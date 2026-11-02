import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
import ticket_service as ts
import metrics, sla
from ai_service import fallback_analysis
from auth_service import register_student, create_staff
from backup import make_backup
from conftest import fix_and_confirm, staff_for
from database import LATEST_VERSION, connect, init_db, schema_version
from healthcheck import check as health
from logging_config import JsonFormatter, setup
from rate_limit import RateLimitError, check as rate_check
from schemas import Status, TicketRecord

PW = "correct-horse-1"
T = "No electricity in Hostel Block B since morning"


def make(db, reporter=None, text=T, loc="Hostel Block B"):
    return ts.create_ticket(fallback_analysis(text), text, loc, "fallback", reporter_id=reporter, db_path=db).ticket


def rec(priority="High", status="Open", created_h_ago=0.0, resolved_h_after=None):
    created = datetime.now(timezone.utc) - timedelta(hours=created_h_ago)
    return TicketRecord(ticket_id="RAI-2026-0001", description="d", summary="s", category="Other", priority=priority, department="General Administration",
                        status=status, ai_mode="fallback", created_at=created, updated_at=created,
                        resolved_at=created + timedelta(hours=resolved_h_after) if resolved_h_after is not None else None)


# ---------------------------------------------------------------- assignment
def test_assign_and_unassign_are_staff_only_and_audited(db):
    st, t = staff_for(db), make(db)
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    with pytest.raises(ts.TicketError):
        ts.assign_ticket(t.ticket_id, st.id, actor=stu, db_path=db)
    with pytest.raises(ts.TicketError, match="only be assigned to staff"):
        ts.assign_ticket(t.ticket_id, stu.id, actor=st, db_path=db)
    assert ts.assign_ticket(t.ticket_id, st.id, actor=st, db_path=db).assignee_id == st.id
    assert ts.assign_ticket(t.ticket_id, None, actor=st, db_path=db).assignee_id is None
    assert [e["detail"] for e in ts.get_events(t.ticket_id, actor=st, db_path=db) if e["action"] == "assignment"] == ["assigned to Test Staff", "unassigned"]
    assert [x.ticket_id for x in ts.list_tickets(unassigned=True, db_path=db)] == [t.ticket_id]


# ---------------------------------------------------------------- notes: internal vs public
def test_internal_notes_never_reach_the_student_but_public_ones_do(db):
    st = staff_for(db)
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    c = ts.create_ticket(fallback_analysis(T), T, None, "fallback", reporter_id=stu.id, db_path=db)
    tid = c.ticket.ticket_id
    ts.add_comment(tid, "Reporter has history of false alarms", "internal", actor=st, db_path=db)
    ts.add_comment(tid, "An electrician is on the way.", "public", actor=st, db_path=db)
    assert ts.latest_public_updates([tid], db_path=db) == {tid: "An electrician is on the way."}
    ps = ts.get_public_status(tid, c.tracking_code, db_path=db)
    assert [u["text"] for u in ps.updates] == ["An electrician is on the way."] and "false alarms" not in json.dumps(ps.model_dump(), default=str)
    tl = ts.get_timeline(tid, actor=st, db_path=db)
    assert {i["kind"] for i in tl} == {"event", "internal", "public"} and [i["at"] for i in tl] == sorted(i["at"] for i in tl)


def test_note_validation_and_permissions(db):
    st, t = staff_for(db), make(db)
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    for body, vis in (("", "public"), ("x" * 1001, "internal"), ("ok", "everyone")):
        with pytest.raises(ts.TicketError):
            ts.add_comment(t.ticket_id, body, vis, actor=st, db_path=db)
    with pytest.raises(ts.TicketError):
        ts.add_comment(t.ticket_id, "hello", "public", actor=stu, db_path=db)


# ---------------------------------------------------------------- bulk actions
def test_bulk_actions_report_partial_failures_honestly(db):
    st = staff_for(db)
    a, b = make(db), make(db, text="Wi-Fi down in library", loc="Library")
    ts.update_status(a.ticket_id, Status.IN_PROGRESS, actor=st, db_path=db)
    ok, failed = ts.bulk_status([a.ticket_id, b.ticket_id, "RAI-2026-9999"], Status.IN_PROGRESS, actor=st, db_path=db)
    assert ok == [b.ticket_id] and set(failed) == {a.ticket_id, "RAI-2026-9999"}  # a is already In Progress
    ok, failed = ts.bulk_assign([a.ticket_id, b.ticket_id], st.id, actor=st, db_path=db)
    assert ok == [a.ticket_id, b.ticket_id] and not failed


# ---------------------------------------------------------------- SLA
def test_sla_states(monkeypatch):
    assert sla.state(rec("High", created_h_ago=1))[0] == "ok"
    assert sla.state(rec("High", created_h_ago=7))[0] == "due_soon"  # under 25% of the 8h window left
    s, hrs = sla.state(rec("High", created_h_ago=10))
    assert s == "overdue" and 1.9 < hrs < 2.1 and sla.label(rec("High", created_h_ago=10)).startswith("Overdue 2h")
    assert sla.state(rec("Medium", "Resolved", created_h_ago=30, resolved_h_after=10))[0] == "met"
    assert sla.state(rec("High", "Resolved", created_h_ago=30, resolved_h_after=20))[0] == "missed"
    monkeypatch.setenv("SLA_HIGH_HOURS", "1")
    assert sla.state(rec("High", created_h_ago=2))[0] == "overdue"  # configurable


def test_fixed_and_resolved_times_are_recorded_separately(db):
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    t = make(db, reporter=stu.id)
    assert ts.get_ticket(t.ticket_id, db).resolved_at is None
    ts.update_status(t.ticket_id, Status.IN_PROGRESS, actor=staff_for(db), db_path=db)
    ts.mark_fixed(t.ticket_id, "Replaced the part", actor=staff_for(db), db_path=db)
    mid = ts.get_ticket(t.ticket_id, db)
    assert mid.fixed_at is not None and mid.resolved_at is None
    ts.student_signoff(t.ticket_id, actor=stu, confirm=True, db_path=db)
    end = ts.get_ticket(t.ticket_id, db)
    assert end.resolved_at is not None and end.fixed_at == mid.fixed_at and end.resolved_by == "student"


# ---------------------------------------------------------------- metrics never invent data
def test_metrics_on_an_empty_database_are_none_not_zero_or_fake(db):
    m = metrics.compute(actor=staff_for(db), db_path=db)
    assert m["total"] == 0 and m["median_resolution_hours"] is None and m["median_first_response_hours"] is None and m["sla_compliance"] is None


def test_metrics_values_and_staff_only(db):
    st = staff_for(db)
    stu = register_student("Asha", "a@c.edu", PW, db_path=db)
    t = make(db, reporter=stu.id)
    fix_and_confirm(db, t.ticket_id, stu, rating=4)
    make(db, text="Wi-Fi down in library", loc="library"); make(db, text="Wi-Fi slow in library", loc="Library")
    m = metrics.compute(actor=st, db_path=db)
    assert m["total"] == 3 and m["resolved"] == 1 and m["open"] == 2 and m["sla_compliance"] == 100 and m["avg_rating"] == 4.0
    assert m["median_fix_hours"] is not None and m["median_resolution_hours"] is not None and m["median_first_response_hours"] is not None
    assert m["top_locations"][0] == ("Library", 2) and sum(n for _, n in m["volume_14d"]) == 3
    with pytest.raises(ts.TicketError):
        metrics.compute(actor=stu, db_path=db)


# ---------------------------------------------------------------- rate limits
def test_rate_limit_counts_per_user_and_window(db):
    for _ in range(3):
        rate_check(1, "analysis", 3, 60, db_path=db)
    with pytest.raises(RateLimitError, match="try again"):
        rate_check(1, "analysis", 3, 60, db_path=db)
    rate_check(2, "analysis", 3, 60, db_path=db)  # another user is unaffected
    rate_check(1, "report", 3, 60, db_path=db)  # another kind is unaffected
    with sqlite3.connect(db) as c:
        c.execute("UPDATE rate_events SET created_at = ?", ((datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat(timespec="seconds"),))
    rate_check(1, "analysis", 3, 60, db_path=db)  # window has passed


# ---------------------------------------------------------------- backup, health, migrations, logging
def test_backup_is_restorable_and_old_ones_are_pruned(db, tmp_path):
    make(db)
    paths = [make_backup(db, str(tmp_path / "bk"), keep=2) for _ in range(3)]
    assert len(list((tmp_path / "bk").glob("*.db"))) == 2 and not paths[0].exists()
    with sqlite3.connect(paths[-1]) as c:
        assert c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1


def test_database_connection_uses_wal_foreign_keys_and_busy_timeout(db):
    with connect(db) as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 10000
        indexes = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {"idx_tickets_created", "idx_tickets_status_created", "idx_tickets_reporter_created", "idx_tickets_assignee_created", "idx_tickets_duplicate"} <= indexes


def test_backup_retention_requires_a_positive_count(db, tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        make_backup(db, str(tmp_path / "bk"), keep=0)


def test_health_check_reports_problems_plainly(db):
    h = health(db)
    assert h["ok"] and h["schema_version"] == LATEST_VERSION
    assert any("no staff account" in i for i in h["issues"]) and any("AI is not configured" in i for i in h["issues"])
    create_staff("Staff Two", "s@c.edu", PW, db_path=db)
    assert not any("no staff account" in i for i in health(db)["issues"])


def test_old_databases_are_upgraded_and_newer_ones_refused(tmp_path):
    old = str(tmp_path / "old.db")
    with sqlite3.connect(old) as c:  # a version-1 style tickets table without the newer columns
        c.execute("CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, description TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL, "
                  "department TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', location TEXT, duplicate_of TEXT, review_required INTEGER NOT NULL DEFAULT 0, "
                  "ai_mode TEXT NOT NULL, tracking_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolution_note TEXT, is_sample INTEGER NOT NULL DEFAULT 0)")
        c.execute("INSERT INTO tickets (ticket_id, description, summary, category, priority, department, ai_mode, tracking_hash, created_at, updated_at) "
                  "VALUES ('RAI-2026-0001','d','s','Other','Low','General Administration','fallback','h','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')")
    init_db(old)
    assert schema_version(old) == LATEST_VERSION
    with sqlite3.connect(old) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(tickets)")}
        assert {"assignee_id", "resolved_at", "reporter_id"} <= cols and c.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1  # data kept
        c.execute("INSERT INTO schema_version VALUES (99, 'x')")
    with pytest.raises(RuntimeError, match="newer"):
        init_db(old)


def test_logs_are_json_and_setup_is_idempotent(capsys):
    lg = setup("INFO"); setup("INFO")
    assert len([h for h in lg.handlers if getattr(h, "_resolveai", False)]) == 1
    rec_ = logging.LogRecord("resolveai.ai", logging.INFO, "", 0, "ai_analysis", (), None)
    rec_.mode, rec_.latency_ms = "llm", 120
    out = json.loads(JsonFormatter().format(rec_))
    assert out["event"] == "ai_analysis" and out["mode"] == "llm" and out["latency_ms"] == 120 and out["level"] == "INFO"
