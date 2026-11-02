import sqlite3
import pytest
from datetime import datetime, timedelta, timezone
from auth_service import MAX_ATTEMPTS, AuthError, authenticate, ensure_bootstrap_staff, register_student, verify_password
from ai_service import fallback_analysis
from ticket_service import create_ticket, list_tickets

PW = "correct-horse-1"


def test_register_and_login_student(db):
    u = register_student("  Asha   Rao ", "Asha@College.EDU ", PW, db_path=db)
    assert u.role == "student" and u.email == "asha@college.edu" and u.name == "Asha Rao"
    assert authenticate("ASHA@college.edu", PW, role="student", db_path=db).id == u.id


def test_password_is_hashed_not_stored(db):
    register_student("Asha Rao", "a@c.edu", PW, db_path=db)
    with sqlite3.connect(db) as c:
        h = c.execute("SELECT password_hash FROM users").fetchone()[0]
    assert PW not in h and h.startswith("scrypt$") and verify_password(PW, h) and not verify_password("nope", h)


@pytest.mark.parametrize("name,email,pw", [("A", "a@c.edu", PW), ("Asha", "not-an-email", PW), ("Asha", "a@c.edu", "short")])
def test_validation_rejects_bad_input(db, name, email, pw):
    with pytest.raises(AuthError):
        register_student(name, email, pw, db_path=db)


def test_duplicate_email_rejected_case_insensitive(db):
    register_student("Asha", "a@c.edu", PW, db_path=db)
    with pytest.raises(AuthError, match="already exists"):
        register_student("Other", "A@C.EDU", PW, db_path=db)


def test_wrong_password_and_unknown_email_look_identical(db):
    register_student("Asha", "a@c.edu", PW, db_path=db)
    with pytest.raises(AuthError) as a:
        authenticate("a@c.edu", "wrong-password", db_path=db)
    with pytest.raises(AuthError) as b:
        authenticate("nobody@c.edu", PW, db_path=db)
    assert str(a.value) == str(b.value)


def test_student_cannot_sign_in_as_staff(db):
    register_student("Asha", "a@c.edu", PW, db_path=db)
    with pytest.raises(AuthError):
        authenticate("a@c.edu", PW, role="staff", db_path=db)


def test_lockout_after_repeated_failures_then_expires(db):
    register_student("Asha", "a@c.edu", PW, db_path=db)
    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(AuthError):
            authenticate("a@c.edu", "bad-password", db_path=db)
    with pytest.raises(AuthError, match="Too many"):
        authenticate("a@c.edu", PW, db_path=db)  # even the right password is refused while locked
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE users SET locked_until = ?", (past,))
    assert authenticate("a@c.edu", PW, db_path=db).role == "student"


def test_staff_creation_is_separate_and_bootstrap_only_when_none_exist(db, monkeypatch):
    monkeypatch.setenv("STAFF_EMAIL", "boss@c.edu"); monkeypatch.setenv("STAFF_PASSWORD", "boss-password-1")
    assert ensure_bootstrap_staff(db_path=db) is True and ensure_bootstrap_staff(db_path=db) is False
    assert authenticate("boss@c.edu", "boss-password-1", role="staff", db_path=db).role == "staff"


def test_tickets_are_linked_to_their_reporter(db):
    a = register_student("Asha", "a@c.edu", PW, db_path=db)
    b = register_student("Ben", "b@c.edu", PW, db_path=db)
    t = "No electricity in Hostel Block B since morning"
    create_ticket(fallback_analysis(t), t, None, "fallback", reporter_id=a.id, db_path=db)
    create_ticket(fallback_analysis(t), t, None, "fallback", reporter_id=b.id, db_path=db)
    assert [x.reporter_id for x in list_tickets(reporter_id=a.id, db_path=db)] == [a.id]
