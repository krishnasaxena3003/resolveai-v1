"""Per-user limits that protect the AI budget and the queue from abuse. Counted in the database, so they survive restarts."""
from datetime import datetime, timedelta, timezone
from database import connect, transaction


class RateLimitError(Exception):
    """Message is safe to show to the person."""


def check(user_id: int, kind: str, max_events: int, window_minutes: int, db_path: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=window_minutes)).isoformat(timespec="seconds")
    with connect(db_path) as c, transaction(c):
        rows = c.execute("SELECT created_at FROM rate_events WHERE user_id = ? AND kind = ? AND created_at >= ? ORDER BY created_at", (user_id, kind, since)).fetchall()
        if len(rows) >= max_events:
            wait = max(1, int((datetime.fromisoformat(rows[0]["created_at"]) + timedelta(minutes=window_minutes) - now).total_seconds() // 60) + 1)
            raise RateLimitError(f"You have reached the limit for now. Please try again in about {wait} minute{'s' if wait != 1 else ''}.")
        c.execute("INSERT INTO rate_events (user_id, kind, created_at) VALUES (?,?,?)", (user_id, kind, now.isoformat(timespec="seconds")))
        c.execute("DELETE FROM rate_events WHERE created_at < ?", ((now - timedelta(days=2)).isoformat(timespec="seconds"),))
