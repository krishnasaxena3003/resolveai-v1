import sqlite3
import pytest
import ticket_service as ts
from ai_service import fallback_analysis
from auth_service import DEMO_PASSWORD, authenticate, create_session, create_staff, ensure_demo_accounts, user_from_session
from conftest import staff_for
from database import LATEST_VERSION, init_db, schema_version
from schemas import Status

V3_TICKETS = """CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, description TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL,
department TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open','In Progress','Resolved')), location TEXT, duplicate_of TEXT, review_required INTEGER NOT NULL DEFAULT 0,
ai_mode TEXT NOT NULL, tracking_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolution_note TEXT, is_sample INTEGER NOT NULL DEFAULT 0,
reporter_id INTEGER, assignee_id INTEGER, resolved_at TEXT)"""


def test_a_version_3_database_is_rebuilt_without_losing_tickets_or_history(tmp_path):
    path = str(tmp_path / "v3.db")
    with sqlite3.connect(path) as c:
        c.execute(V3_TICKETS)
        c.execute("CREATE TABLE ticket_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL REFERENCES tickets(ticket_id), actor_id INTEGER, actor_role TEXT NOT NULL, action TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL)")
        c.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL)")
        c.execute("INSERT INTO schema_version VALUES (3, 'x')")
        for i, st in enumerate(("Open", "In Progress", "Resolved"), 1):
            c.execute("INSERT INTO tickets (ticket_id, description, summary, category, priority, department, status, ai_mode, tracking_hash, created_at, updated_at, resolved_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (f"RAI-2026-000{i}", f"d{i}", f"s{i}", "Other", "Low", "General Administration", st, "fallback", "h", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00" if st == "Resolved" else None))
        c.execute("INSERT INTO ticket_events (ticket_id, actor_id, actor_role, action, detail, created_at) VALUES ('RAI-2026-0002', 1, 'staff', 'status', 'Open → In Progress', 'x')")
    init_db(path)
    assert schema_version(path) == LATEST_VERSION
    with sqlite3.connect(path) as c:
        assert [r[0] for r in c.execute("SELECT status FROM tickets ORDER BY ticket_id")] == ["Open", "In Progress", "Resolved"]
        assert c.execute("SELECT COUNT(*) FROM ticket_events").fetchone()[0] == 1 and c.execute("PRAGMA foreign_key_check").fetchall() == []
        c.execute("UPDATE tickets SET status = 'Pending Sign-off', reopen_count = 2 WHERE ticket_id = 'RAI-2026-0001'")  # new statuses and columns now work
        assert c.execute("SELECT name FROM sqlite_master WHERE name = 'attachments'").fetchone()
        indexes = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        assert {"idx_tickets_status", "idx_tickets_reporter", "idx_tickets_assignee", "idx_users_worker_alert_recipients"} <= indexes
    init_db(path)  # running it again is a no-op


def test_demo_accounts_exist_only_in_demo_mode(db, monkeypatch):
    assert ensure_demo_accounts(db_path=db) is False
    monkeypatch.setenv("DEMO_MODE", "1")
    assert ensure_demo_accounts(db_path=db) is True and ensure_demo_accounts(db_path=db) is True  # idempotent
    u = authenticate("plumbing@demo.test", DEMO_PASSWORD, role="staff", db_path=db)
    assert u.department == "Plumbing" and authenticate("student@demo.test", DEMO_PASSWORD, role="student", db_path=db).role == "student"
    assert user_from_session(create_session(u.id, db_path=db), db_path=db).department == "Plumbing"


def test_staff_departments_are_stored_and_listed(db):
    create_staff("Mario Vance", "m@c.edu", "correct-horse-1", department="Plumbing", db_path=db)
    st = staff_for(db)
    depts = {u.name: u.department for u in ts.list_staff(actor=st, db_path=db)}
    assert depts["Mario Vance"] == "Plumbing" and depts["Test Staff"] is None


def test_new_statuses_are_accepted_by_the_database(db):
    t = ts.create_ticket(fallback_analysis("No electricity in the hostel"), "No electricity in the hostel", None, "fallback", db_path=db).ticket
    with sqlite3.connect(db) as c:
        for s in (Status.PENDING, Status.REOPENED):
            c.execute("UPDATE tickets SET status = ? WHERE ticket_id = ?", (s.value, t.ticket_id))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE tickets SET status = 'Teleported' WHERE ticket_id = ?", (t.ticket_id,))
