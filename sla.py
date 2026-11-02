"""Service-level targets. The clock runs from submission until staff mark the issue fixed (the student's confirmation is not staff time)."""
from datetime import datetime, timedelta, timezone
from config import get_settings
from schemas import LIVE_STATUSES, Priority, TicketRecord


def sla_hours(priority: Priority) -> float:
    s = get_settings()
    return {Priority.HIGH: s.sla_high_hours, Priority.MEDIUM: s.sla_medium_hours, Priority.LOW: s.sla_low_hours}[priority]


def due_at(t: TicketRecord) -> datetime:
    # Persisted targets survive priority or configuration changes. Legacy tickets
    # without a stored target continue to use their original configured SLA.
    return t.deadline_at or (t.created_at + timedelta(hours=sla_hours(t.priority)))


def completed_at(t: TicketRecord) -> datetime:
    return t.fixed_at or t.resolved_at or t.updated_at


def state(t: TicketRecord, now: datetime | None = None) -> tuple[str, float]:
    """Returns (state, hours). States: met, missed (fixed or closed), overdue (hours late), due_soon / ok (hours left)."""
    now = now or datetime.now(timezone.utc)
    if t.status not in LIVE_STATUSES:
        return ("met" if completed_at(t) <= due_at(t) else "missed"), 0.0
    left = (due_at(t) - now).total_seconds() / 3600
    if left < 0:
        return "overdue", -left
    return ("due_soon" if left < 0.25 * sla_hours(t.priority) else "ok"), left


def is_overdue(t: TicketRecord, now: datetime | None = None) -> bool:
    return state(t, now)[0] == "overdue"


def _span(h: float) -> str:
    return f"{h * 60:.0f}m" if h < 1 else f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"


def label(t: TicketRecord, now: datetime | None = None) -> str:
    st, h = state(t, now)
    return {"met": "SLA met", "missed": "SLA missed", "overdue": f"Overdue {_span(h)}", "due_soon": f"Due in {_span(h)}", "ok": f"Due in {_span(h)}"}[st]
