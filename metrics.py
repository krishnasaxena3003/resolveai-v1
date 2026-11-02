"""Operational metrics for staff, computed only from stored tickets. Definitions (shown in the UI):
- First response: hours from submission to the first staff action on the ticket (assignment, status change, correction or note).
- Time to fix: hours from submission to the moment staff marked the issue fixed. Median, because a few slow tickets distort the mean.
- Time to close: hours from submission to the student's confirmation (or a timed close).
- Fixed within target: share of fixed or closed tickets completed within the target for their priority.
- Reopen rate: share of fixed or closed tickets that a student reopened at least once.
- Satisfaction: average of the optional 1 to 5 ratings students give when they confirm a fix.
Values are None, never invented, when there is not enough data."""
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from database import connect
from schemas import LIVE_STATUSES, Status, User
from sla import state
from ticket_service import _require_staff, list_tickets


def _med(xs):
    return round(statistics.median(xs), 1) if xs else None


def compute(*, actor: User, db_path=None, now: datetime | None = None) -> dict:
    _require_staff(actor, db_path)
    now = now or datetime.now(timezone.utc)
    ts = list_tickets(db_path=db_path)
    live = [t for t in ts if t.status in LIVE_STATUSES]
    done = [t for t in ts if t.status in (Status.PENDING, Status.RESOLVED) or t.reopen_count]
    closed = [t for t in ts if t.status == Status.RESOLVED]
    with connect(db_path) as c:
        firsts = c.execute("SELECT t.created_at AS c, MIN(e.created_at) AS f FROM tickets t JOIN ticket_events e ON e.ticket_id = t.ticket_id "
                           "WHERE e.actor_role IN ('staff','worker') GROUP BY t.ticket_id").fetchall()
    states = [state(t, now)[0] for t in ts if t.status not in LIVE_STATUSES and t.status != Status.WITHDRAWN]
    met, missed = states.count("met"), states.count("missed")
    days = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
    per_day = Counter(t.created_at.date() for t in ts)
    locs = Counter((t.location or "").strip().title() for t in ts if (t.location or "").strip())
    ratings = [t.rating for t in ts if t.rating]
    return {
        "total": len(ts), "open": sum(t.status == Status.OPEN for t in ts), "in_progress": sum(t.status == Status.IN_PROGRESS for t in ts),
        "pending": sum(t.status == Status.PENDING for t in ts), "reopened": sum(t.status == Status.REOPENED for t in ts), "resolved": len(closed),
        "overdue": sum(state(t, now)[0] == "overdue" for t in ts), "unassigned": sum(t.assignee_id is None for t in live),
        "needs_review": sum(t.review_required for t in live),
        "median_fix_hours": _med([(t.fixed_at - t.created_at).total_seconds() / 3600 for t in ts if t.fixed_at]),
        "median_resolution_hours": _med([((t.resolved_at or t.updated_at) - t.created_at).total_seconds() / 3600 for t in closed]),
        "median_first_response_hours": _med([(datetime.fromisoformat(r["f"]) - datetime.fromisoformat(r["c"])).total_seconds() / 3600 for r in firsts]),
        "sla_compliance": round(100 * met / (met + missed)) if met + missed else None,
        "reopen_rate": round(100 * sum(t.reopen_count > 0 for t in done) / len(done)) if done else None,
        "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None, "rating_count": len(ratings),
        "closed_by_student": sum(t.resolved_by == "student" for t in closed),
        "volume_14d": [(d, per_day.get(d, 0)) for d in days], "top_locations": locs.most_common(5),
        "ai_llm": sum(t.ai_mode == "llm" for t in ts), "ai_fallback": sum(t.ai_mode == "fallback" for t in ts),
    }
