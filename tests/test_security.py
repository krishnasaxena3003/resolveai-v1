"""Server-side protections: role checks in the service layer, audit trail, sessions, reset codes, lookup lockout."""
import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
import ticket_service as ts
from ai_service import fallback_analysis
from analytics import to_csv
from auth_service import (AuthError, authenticate, create_session, create_staff, end_session, issue_reset_code, redeem_reset,
                          register_student, set_password, user_from_session)
from schemas import Category, Priority, Status, User
from conftest import staff_for

PW = "correct-horse-1"
T = "No electricity in Hostel Block B since morning"


def make(db, reporter=None):
    return ts.create_ticket(fallback_analysis(T), T, "Hostel Block B", "fallback", reporter_id=reporter, db_path=db).ticket


# ---------------------------------------------------------------- role enforcement below the UI
def test_students_and_unknown_actors_cannot_run_staff_operations(db):
    t = make(db)
    student = register_student("Asha", "a@c.edu", PW, db_path=db)
    ghost = User(id=9999, name="Ghost", email="g@c.edu", role="staff")  # claims staff but is not in the database
    for actor in (student, ghost, None):
        with pytest.raises(ts.TicketError, match="staff"):
            ts.update_status(t.ticket_id, Status.IN_PROGRESS, actor=actor, db_path=db)
        with pytest.raises(ts.TicketError):
            ts.correct_fields(t.ticket_id, Category.OTHER, Priority.LOW, "Plumbing", actor=actor, db_path=db)
        with pytest.raises(ts.TicketError):
            ts.staff_list_tickets(actor=actor, db_path=db)
        with pytest.raises(ts.TicketError):
            ts.get_events(t.ticket_id, actor=actor, db_path=db)
    assert ts.get_ticket(t.ticket_id, db).status == Status.OPEN


def test_a_forged_staff_role_object_is_not_trusted(db):
    t = make(db)
    s = register_student("Asha", "a@c.edu", PW, db_path=db)
    forged = User(id=s.id, name=s.name, email=s.email, role="staff")  # same id as a real student, role field edited
    with pytest.raises(ts.TicketError):
        ts.update_status(t.ticket_id, Status.IN_PROGRESS, actor=forged, db_path=db)


# ---------------------------------------------------------------- audit trail
def test_every_change_is_recorded_with_who_did_it(db):
    st = staff_for(db)
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    t = make(db, reporter=stu.id)
    ts.correct_fields(t.ticket_id, Category.HOSTEL, Priority.LOW, "Hostel Maintenance", actor=st, db_path=db)
    ts.update_status(t.ticket_id, Status.IN_PROGRESS, actor=st, db_path=db)
    ts.update_status(t.ticket_id, Status.PENDING, "Fuse replaced", actor=st, db_path=db)
    ts.student_signoff(t.ticket_id, actor=stu, confirm=True, db_path=db)
    ev = ts.get_events(t.ticket_id, actor=st, db_path=db)
    assert [e["action"] for e in ev] == ["created", "correction", "status", "status", "status"]
    assert ev[0]["who"] == "Asha" and ev[1]["who"] == "Test Staff" and "Fuse replaced" in ev[3]["detail"] and ev[4]["who"] == "Asha"
    assert "category" in ev[1]["detail"] and "→" in ev[2]["detail"]


def test_failed_updates_leave_no_audit_event(db):
    st = staff_for(db)
    t = make(db)
    with pytest.raises(ts.TicketError):
        ts.update_status(t.ticket_id, Status.RESOLVED, actor=st, db_path=db)  # illegal jump
    assert [e["action"] for e in ts.get_events(t.ticket_id, actor=st, db_path=db)] == ["created"]


# ---------------------------------------------------------------- guest lookup lockout (server side)
def test_tracking_code_guessing_is_locked_out_in_the_database(db):
    c = ts.create_ticket(fallback_analysis(T), T, None, "fallback", db_path=db)
    tid = c.ticket.ticket_id
    for _ in range(ts.LOOKUP_MAX):
        assert ts.get_public_status(tid, "AAAA-0000", db_path=db) is None
    with pytest.raises(ts.TicketError, match="Too many"):
        ts.get_public_status(tid, c.tracking_code, db_path=db)  # even the right code is refused while locked
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE lookup_attempts SET locked_until = ?", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),))
    assert ts.get_public_status(tid, c.tracking_code, db_path=db) is not None


def test_malformed_ticket_ids_are_ignored_without_storing_anything(db):
    assert ts.get_public_status("DROP TABLE x", "AAAA-0000", db_path=db) is None
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lookup_attempts").fetchone()[0] == 0


# ---------------------------------------------------------------- sessions
def test_session_roundtrip_expiry_and_revocation(db):
    u = register_student("Asha", "a@c.edu", PW, db_path=db)
    tok = create_session(u.id, db_path=db)
    assert user_from_session(tok, db_path=db).id == u.id and user_from_session("nonsense", db_path=db) is None
    with sqlite3.connect(db) as conn:
        assert tok not in str(conn.execute("SELECT * FROM sessions").fetchall())  # only a hash is stored
        conn.execute("UPDATE sessions SET expires_at = ?", ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
    assert user_from_session(tok, db_path=db) is None  # expired
    tok2 = create_session(u.id, db_path=db)
    end_session(tok2, db_path=db)
    assert user_from_session(tok2, db_path=db) is None  # revoked on sign-out


# ---------------------------------------------------------------- password reset
def test_staff_issue_a_single_use_code_and_it_signs_the_student_out_everywhere(db):
    st = staff_for(db)
    u = register_student("Asha", "a@c.edu", PW, db_path=db)
    tok = create_session(u.id, db_path=db)
    code = issue_reset_code("A@c.edu", actor=st, db_path=db)
    redeem_reset("a@c.edu", code.lower(), "brand-new-pass-2", db_path=db)
    assert authenticate("a@c.edu", "brand-new-pass-2", db_path=db).id == u.id
    with pytest.raises(AuthError):
        authenticate("a@c.edu", PW, db_path=db)  # old password is dead
    assert user_from_session(tok, db_path=db) is None  # old sessions revoked
    with pytest.raises(AuthError, match="not valid"):
        redeem_reset("a@c.edu", code, "another-pass-3", db_path=db)  # single use


def test_students_cannot_issue_codes_and_staff_cannot_be_reset_this_way(db):
    st = staff_for(db)
    s1 = register_student("Asha", "a@c.edu", PW, db_path=db)
    register_student("Ben", "b@c.edu", PW, db_path=db)
    with pytest.raises(AuthError, match="Only staff"):
        issue_reset_code("b@c.edu", actor=s1, db_path=db)
    with pytest.raises(AuthError, match="No student"):
        issue_reset_code(st.email, actor=st, db_path=db)


def test_wrong_codes_lock_and_expired_codes_fail(db):
    st = staff_for(db)
    register_student("Asha", "a@c.edu", PW, db_path=db)
    code = issue_reset_code("a@c.edu", actor=st, db_path=db)
    for _ in range(5):
        with pytest.raises(AuthError):
            redeem_reset("a@c.edu", "0000-0000", "brand-new-pass-2", db_path=db)
    with pytest.raises(AuthError, match="Too many"):
        redeem_reset("a@c.edu", code, "brand-new-pass-2", db_path=db)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE users SET locked_until = NULL, reset_expires = ?", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),))
    with pytest.raises(AuthError, match="not valid"):
        redeem_reset("a@c.edu", code, "brand-new-pass-2", db_path=db)  # right code, but expired


def test_admin_command_line_password_reset(db):
    st = staff_for(db)
    set_password(st.email, "fresh-admin-pass-9", db_path=db)
    assert authenticate(st.email, "fresh-admin-pass-9", role="staff", db_path=db).role == "staff"
    with pytest.raises(AuthError):
        set_password("nobody@c.edu", "fresh-admin-pass-9", db_path=db)


# ---------------------------------------------------------------- sign-up restriction and export
def test_email_domain_restriction(db, monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "college.edu, @uni.ac.in")
    with pytest.raises(AuthError, match="college email"):
        register_student("Asha", "asha@gmail.com", PW, db_path=db)
    assert register_student("Asha", "asha@college.edu", PW, db_path=db).role == "student"
    assert register_student("Ben", "ben@uni.ac.in", PW, db_path=db).role == "student"
    create_staff("Admin", "admin@gmail.com", PW, db_path=db)  # staff are admin-created, so the rule does not apply


def test_csv_export_blocks_spreadsheet_formula_injection(db):
    evil = "=HYPERLINK(\"http://evil\",\"click\") in room 4"
    t = ts.create_ticket(fallback_analysis(evil), evil, "@home", "fallback", db_path=db).ticket
    out = to_csv([t])
    assert "'=HYPERLINK" in out and ",'@home," in out and out.splitlines()[0].startswith("ticket_id,")
