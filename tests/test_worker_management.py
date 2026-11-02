import sqlite3

import pytest

from ai_service import fallback_analysis
from auth_service import (AuthError, authenticate, create_session, create_worker, delete_worker_account,
                          list_worker_accounts, list_worker_contacts, register_student, update_worker_account, user_from_session)
from conftest import staff_for
from database import connect, init_db
from pages_campus import _render_map
from ticket_service import TicketError, assign_ticket, create_ticket


def _ticket(db, description="No electricity in hostel corridor"):
    return create_ticket(fallback_analysis(description), description, "Hostel Block B (Boys)",
                         "fallback", db_path=db).ticket


def test_staff_can_update_worker_identity_and_release_work_on_team_change(db):
    admin = staff_for(db)
    worker = create_worker("Hostel Worker", "worker@t.edu", "worker-password-1",
                           "Hostel Maintenance", db_path=db, phone="+919999000001")
    ticket = _ticket(db)
    assign_ticket(ticket.ticket_id, worker.id, actor=admin, db_path=db)
    token = create_session(worker.id, db_path=db)

    update_worker_account(worker.id, "Network Technician", "network@t.edu", "IT/Network Support",
                          "+919999000002", actor=admin, new_password="new-worker-pass-1", db_path=db)

    updated = authenticate("network@t.edu", "new-worker-pass-1", role="worker",
                           occupation="IT/Network Support", db_path=db)
    assert updated.name == "Network Technician"
    assert user_from_session(token, db_path=db) is None
    with pytest.raises(AuthError):
        authenticate("worker@t.edu", "worker-password-1", role="worker", occupation="Hostel Maintenance", db_path=db)
    with connect(db) as conn:
        row = conn.execute("SELECT assignee_id FROM tickets WHERE ticket_id=?", (ticket.ticket_id,)).fetchone()
        event = conn.execute("SELECT action,detail FROM ticket_events WHERE ticket_id=? ORDER BY id DESC LIMIT 1", (ticket.ticket_id,)).fetchone()
    assert row["assignee_id"] is None
    assert event["action"] == "assignment" and "team changed" in event["detail"]


def test_removing_worker_revokes_login_clears_phone_and_preserves_ticket_history(db):
    admin = staff_for(db)
    worker = create_worker("Safety Worker", "safety@t.edu", "safety-password-1",
                           "Campus Safety & Emergency Response", db_path=db, phone="+919999000003")
    ticket = _ticket(db, "Fire door needs repair")
    assign_ticket(ticket.ticket_id, worker.id, actor=admin, db_path=db)
    token = create_session(worker.id, db_path=db)

    released = delete_worker_account(worker.id, actor=admin, db_path=db)

    assert released == 1 and user_from_session(token, db_path=db) is None
    with pytest.raises(AuthError):
        authenticate("safety@t.edu", "safety-password-1", role="worker",
                     occupation="Campus Safety & Emergency Response", db_path=db)
    assert list_worker_contacts(actor=admin, db_path=db) == []
    account = next(row for row in list_worker_accounts(actor=admin, db_path=db) if row["id"] == worker.id)
    assert account["is_active"] == 0 and account["phone"] is None
    with connect(db) as conn:
        row = conn.execute("SELECT assignee_id FROM tickets WHERE ticket_id=?", (ticket.ticket_id,)).fetchone()
        event = conn.execute("SELECT action,detail FROM ticket_events WHERE ticket_id=? ORDER BY id DESC LIMIT 1", (ticket.ticket_id,)).fetchone()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert row["assignee_id"] is None
    assert event["action"] == "assignment" and "account was removed" in event["detail"]


def test_inactive_worker_cannot_be_assigned_or_receive_sms_contacts(db):
    admin = staff_for(db)
    worker = create_worker("Inactive Worker", "inactive@t.edu", "inactive-password-1",
                           "Hostel Maintenance", db_path=db)
    delete_worker_account(worker.id, actor=admin, db_path=db)
    ticket = _ticket(db)
    with pytest.raises(TicketError, match="only be assigned"):
        assign_ticket(ticket.ticket_id, worker.id, actor=admin, db_path=db)
    assert list_worker_contacts(actor=admin, db_path=db) == []


def test_students_cannot_edit_or_remove_worker_accounts(db):
    worker = create_worker("Protected Worker", "protected@t.edu", "protected-password-1",
                           "Hostel Maintenance", db_path=db)
    student = register_student("Student", "student@t.edu", "student-password-1", db_path=db)
    with pytest.raises(AuthError, match="Only staff admins"):
        update_worker_account(worker.id, "Changed Name", "changed@t.edu", "Hostel Maintenance", None,
                              actor=student, db_path=db)
    with pytest.raises(AuthError, match="Only staff admins"):
        delete_worker_account(worker.id, actor=student, db_path=db)


def test_v15_database_migration_marks_existing_workers_active(tmp_path):
    path = str(tmp_path / "v15.db")
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE, role TEXT NOT NULL, password_hash TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, created_at TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0, reset_hash TEXT, reset_expires TEXT, department TEXT, phone TEXT)""")
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES (15,'x')")
        conn.execute("INSERT INTO users (name,email,role,password_hash,created_at,department,phone) VALUES ('Old Worker','old@t.edu','worker','hash','x','Plumbing','+919999000004')")
    init_db(path)
    with connect(path) as conn:
        user = conn.execute("SELECT is_active FROM users WHERE email='old@t.edu'").fetchone()
        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 16
    assert user["is_active"] == 1
    assert "idx_users_active_worker_alert_recipients" in indexes


def test_worker_campus_map_omits_ticket_details(db):
    # Use the existing in-memory catalog shape, but make the supplied ticket text a sentinel.
    with connect() as conn:
        locations = [dict(row) for row in conn.execute("SELECT * FROM campus_locations")]
    from types import SimpleNamespace
    private_ticket = SimpleNamespace(ticket_id="PRIVATE-42", description="confidential worker incident", location="hostel")
    rendered = _render_map(locations, [private_ticket], "Campus Locations", None,
                           catalog=locations, show_ticket_counts=False).get_root().render()
    assert "PRIVATE-42" not in rendered and "confidential worker incident" not in rendered
