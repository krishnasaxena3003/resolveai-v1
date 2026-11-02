"""Chart data computed only from tickets currently stored in SQLite."""
import csv
import io
import pandas as pd
from schemas import Category, Status, TicketRecord


def counts(tickets: list[TicketRecord]) -> dict:
    by_cat = {c.value: 0 for c in Category}
    by_status = {s.value: 0 for s in Status}
    for t in tickets:
        by_cat[t.category.value] += 1
        by_status[t.status.value] += 1
    return {"category": pd.DataFrame({"Category": list(by_cat), "Tickets": list(by_cat.values())}),
            "status": pd.DataFrame({"Status": list(by_status), "Tickets": list(by_status.values())}),
            "total": len(tickets), "review": sum(t.review_required and t.status not in (Status.RESOLVED, Status.WITHDRAWN) for t in tickets),
            "linked": sum(bool(t.duplicate_of) for t in tickets)}


def _safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s  # stop spreadsheet formula injection


def to_csv(tickets: list[TicketRecord]) -> str:
    buf, w = io.StringIO(), None
    w = csv.writer(buf)
    w.writerow(["ticket_id", "created_at", "status", "category", "priority", "department", "summary", "location", "duplicate_of", "review_required", "withdrawal_review", "withdrawal_reason", "ai_mode", "resolution_note", "description"])
    for t in tickets:
        w.writerow([_safe(x) for x in (t.ticket_id, t.created_at.isoformat(), t.status.value, t.category.value, t.priority.value, t.department, t.summary,
                                      t.location, t.duplicate_of, t.review_required, t.withdrawal_review, t.withdrawal_reason, t.ai_mode, t.resolution_note, t.description)])
    return buf.getvalue()
