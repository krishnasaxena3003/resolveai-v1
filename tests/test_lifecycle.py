"""The fix -> student sign-off handshake, and what each side may do."""
import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
import sla
import ticket_service as ts
from ai_service import fallback_analysis
from auth_service import register_student
from conftest import fix_and_confirm, staff_for
from schemas import Category, Priority, Status

PW = "correct-horse-1"
T = "No electricity in Hostel Block B since morning"


def setup(db):
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    t = ts.create_ticket(fallback_analysis(T), T, "Hostel Block B", "fallback", reporter_id=stu.id, db_path=db).ticket
    return stu, t, staff_for(db)


def pend(db, st, t):
    ts.update_status(t.ticket_id, Status.IN_PROGRESS, actor=st, db_path=db)
    return ts.mark_fixed(t.ticket_id, "Replaced the faulty fuse and tested.", actor=st, db_path=db)


def test_student_confirms_the_fix_and_the_ticket_closes_with_a_rating(db):
    stu, t, st = setup(db)
    pend(db, st, t)
    r = ts.student_signoff(t.ticket_id, actor=stu, confirm=True, comment="Works now, thanks", rating=5, db_path=db)
    assert r.status == Status.RESOLVED and r.resolved_by == "student" and r.rating == 5 and r.resolved_at is not None
    assert "Works now" in ts.student_timeline(t.ticket_id, actor=stu, db_path=db)[-1]["text"]


def test_student_reopens_with_a_reason_and_staff_can_fix_it_again(db):
    stu, t, st = setup(db)
    pend(db, st, t)
    with pytest.raises(ts.TicketError, match="still wrong"):
        ts.student_signoff(t.ticket_id, actor=stu, confirm=False, comment="no", db_path=db)
    r = ts.student_signoff(t.ticket_id, actor=stu, confirm=False, comment="The corridor lights are still dead", db_path=db)
    assert r.status == Status.REOPENED and r.reopen_count == 1 and r.fixed_at is None
    assert sla.state(r)[0] in ("ok", "due_soon", "overdue")  # a reopened ticket is live again, not 'met'
    assert ts.mark_fixed(t.ticket_id, "Replaced the corridor circuit breaker", actor=st, db_path=db).status == Status.PENDING


def test_only_the_owner_can_sign_off_and_only_when_pending(db):
    stu, t, st = setup(db)
    other = register_student("Ben", "b@c.edu", PW, db_path=db)
    with pytest.raises(ts.TicketError, match="not waiting"):
        ts.student_signoff(t.ticket_id, actor=stu, confirm=True, db_path=db)  # not pending yet
    pend(db, st, t)
    for actor in (other, st, None):
        with pytest.raises(ts.TicketError, match="Only the student"):
            ts.student_signoff(t.ticket_id, actor=actor, confirm=True, db_path=db)
    assert ts.get_ticket(t.ticket_id, db).status == Status.PENDING
    with pytest.raises(ts.TicketError, match="between 1 and 5"):
        ts.student_signoff(t.ticket_id, actor=stu, confirm=True, rating=9, db_path=db)


def test_student_can_resolve_their_own_ticket_at_any_time(db):
    stu, t, st = setup(db)
    other = register_student("Ben", "b@c.edu", PW, db_path=db)
    with pytest.raises(ts.TicketError):
        ts.student_resolve(t.ticket_id, "mine now", actor=other, db_path=db)
    r = ts.student_resolve(t.ticket_id, "The power came back by itself", actor=stu, db_path=db)
    assert r.status == Status.RESOLVED and r.resolved_by == "student"
    with pytest.raises(ts.TicketError, match="already resolved"):
        ts.student_resolve(t.ticket_id, actor=stu, db_path=db)
    assert any("came back" in e["detail"] for e in ts.get_events(t.ticket_id, actor=st, db_path=db) if e["action"] == "status")


def test_staff_can_close_an_unanswered_fix_only_after_the_waiting_period(db):
    stu, t, st = setup(db)
    pend(db, st, t)
    with pytest.raises(ts.TicketError, match="more day"):
        ts.close_unconfirmed(t.ticket_id, actor=st, db_path=db)
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds")
    with sqlite3.connect(db) as c:
        c.execute("UPDATE tickets SET fixed_at = ?", (old,))
    with pytest.raises(ts.TicketError):
        ts.close_unconfirmed(t.ticket_id, actor=stu, db_path=db)  # students cannot use the staff path
    r = ts.close_unconfirmed(t.ticket_id, actor=st, db_path=db)
    assert r.status == Status.RESOLVED and r.resolved_by == "staff_timeout"


def test_students_never_see_internal_notes_corrections_or_links(db):
    stu, t, st = setup(db)
    ts.add_comment(t.ticket_id, "Reporter is a known prankster", "internal", actor=st, db_path=db)
    ts.add_comment(t.ticket_id, "An electrician is on the way", "public", actor=st, db_path=db)
    ts.correct_fields(t.ticket_id, Category.HOSTEL, Priority.LOW, "Hostel Maintenance", actor=st, db_path=db)
    tl = ts.student_timeline(t.ticket_id, actor=stu, db_path=db)
    text = " ".join(i["text"] for i in tl)
    assert "electrician" in text and "prankster" not in text and "category" not in text
    assert {i["kind"] for i in tl} <= {"event", "staff", "student"}


def test_student_comments_reach_staff_and_respect_limits_and_closure(db):
    stu, t, st = setup(db)
    ts.add_student_comment(t.ticket_id, "It is getting worse", actor=stu, db_path=db)
    assert any(i["kind"] == "student" and "worse" in i["text"] for i in ts.get_timeline(t.ticket_id, actor=st, db_path=db))
    for body in ("", "x" * 1001):
        with pytest.raises(ts.TicketError):
            ts.add_student_comment(t.ticket_id, body, actor=stu, db_path=db)
    fix_and_confirm(db, t.ticket_id, stu)
    with pytest.raises(ts.TicketError, match="closed"):
        ts.add_student_comment(t.ticket_id, "one more thing", actor=stu, db_path=db)
