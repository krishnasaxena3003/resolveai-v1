"""Ticket operations. Every write is verified by reading the record back.
Staff-only operations check the actor's role in the database (not just in the UI) and write an audit event."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from auth_service import is_staff, is_staff_or_worker, is_student, is_worker
from config import get_settings
from database import COLUMNS, connect, transaction
from schemas import (ALLOWED_TRANSITIONS, AnalysisResult, Category, CreatedTicket, DEPARTMENTS, LIVE_STATUSES, Priority, SAFETY_DEPARTMENT,
                     PublicStatus, Status, TicketRecord, User)

LOOKUP_MAX, LOOKUP_LOCK_MIN = 5, 10
WITHDRAWAL_REASONS = ("Submitted by mistake", "Duplicate report", "Issue already fixed", "Other")
WITHDRAWAL_WINDOW_MINUTES = 5
WITHDRAWAL_REVIEW_THRESHOLD = 3  # flag the third withdrawal within a rolling 7-day window
_ID = re.compile(r"^RAI-\d{4}-\d{4}$")


class TicketError(Exception):
    """Raised with a user-safe message. Never include raw database errors."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(code: str) -> str:
    return hashlib.sha256("".join(ch for ch in code.upper() if ch.isalnum()).encode()).hexdigest()


def _record(row) -> TicketRecord:
    return TicketRecord.model_validate(dict(row))


def _event(c, ticket_id, actor_id, role, action, detail=None):
    c.execute("INSERT INTO ticket_events (ticket_id, actor_id, actor_role, action, detail, created_at) VALUES (?,?,?,?,?,?)",
              (ticket_id, actor_id, role, action, detail, _now()))


def _require_staff(actor: User | None, db_path=None) -> User:
    if actor is None or not is_staff(actor.id, db_path):
        raise TicketError("Only signed-in staff can do this.")
    return actor


def _require_assigned_worker(actor: User | None, ticket: TicketRecord | None, db_path=None) -> User:
    if actor is None or ticket is None or not is_worker(actor.id, db_path) or ticket.assignee_id != actor.id:
        raise TicketError("Only staff admins or the worker assigned to this ticket can perform that action.")
    return actor


def get_ticket(ticket_id: str, db_path: str | None = None) -> TicketRecord | None:
    with connect(db_path) as c:
        row = c.execute(f"SELECT {COLUMNS} FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return _record(row) if row else None


def list_tickets(status=None, category=None, priority=None, department=None, search=None, reporter_id=None, assignee_id=None, unassigned=False, db_path=None) -> list[TicketRecord]:
    """Internal listing (duplicate search, a student's own reports). Staff screens use staff_list_tickets."""
    sql, args = f"SELECT {COLUMNS} FROM tickets WHERE 1=1", []
    for col, val in (("status", status), ("category", category), ("priority", priority), ("department", department)):
        if val:
            sql += f" AND {col} = ?"
            args.append(getattr(val, "value", val))
    if reporter_id is not None:
        sql += " AND reporter_id = ?"
        args.append(reporter_id)
    if assignee_id is not None:
        sql += " AND assignee_id = ?"
        args.append(assignee_id)
    if unassigned:
        sql += " AND assignee_id IS NULL"
    if search:
        sql += " AND (ticket_id LIKE ? OR summary LIKE ? OR description LIKE ? OR location LIKE ?)"
        args += [f"%{search}%"] * 4
    with connect(db_path) as c:
        return [_record(r) for r in c.execute(sql + " ORDER BY created_at DESC, ticket_id DESC", args)]


def staff_list_tickets(*, actor: User, db_path=None, **filters) -> list[TicketRecord]:
    _require_staff(actor, db_path)
    return list_tickets(db_path=db_path, **filters)


def staff_critical_tickets(*, actor: User, db_path=None) -> list[TicketRecord]:
    """Safety queue only; all-department admins and safety responders can access it."""
    _require_staff(actor, db_path)
    if actor.department not in (None, SAFETY_DEPARTMENT):
        return []
    placeholders = ",".join("?" for _ in LIVE_STATUSES)
    args = [1, *(status.value for status in LIVE_STATUSES)]
    sql = f"SELECT {COLUMNS} FROM tickets WHERE critical_alert=? AND status IN ({placeholders})"
    if actor.department:
        sql += " AND department=?"
        args.append(SAFETY_DEPARTMENT)
    with connect(db_path) as conn:
        return [_record(r) for r in conn.execute(sql + " ORDER BY deadline_at, created_at", args)]


def worker_list_tasks(*, actor: User, db_path=None) -> list[TicketRecord]:
    """A worker sees their assignments and unassigned live tickets for their occupation/team."""
    if not is_worker(actor.id, db_path) or not actor.department:
        raise TicketError("Only signed-in workers with an occupation can view worker tasks.")
    worker_statuses = (*LIVE_STATUSES, Status.PENDING)
    assigned_q = ",".join("?" for _ in worker_statuses)
    live_q = ",".join("?" for _ in LIVE_STATUSES)
    args = [actor.id, *(status.value for status in worker_statuses), actor.department, *(status.value for status in LIVE_STATUSES)]
    sql = (f"SELECT {COLUMNS} FROM tickets WHERE ((assignee_id=? AND status IN ({assigned_q})) "
           f"OR (assignee_id IS NULL AND department=? AND status IN ({live_q}))) "
           "ORDER BY critical_alert DESC, deadline_at, created_at")
    with connect(db_path) as conn:
        return [_record(r) for r in conn.execute(sql, args)]


def claim_worker_task(ticket_id: str, *, actor: User, db_path=None) -> TicketRecord:
    """Allow a worker to claim an unassigned live item from their own occupation queue."""
    if not is_worker(actor.id, db_path) or not actor.department:
        raise TicketError("Only signed-in workers with an occupation can claim tasks.")
    t = get_ticket(ticket_id, db_path)
    if not t or t.department != actor.department or t.status not in LIVE_STATUSES:
        raise TicketError("This task is not available to your occupation.")
    if t.assignee_id == actor.id:
        return t
    if t.assignee_id is not None:
        raise TicketError("Another worker has already claimed this task.")
    try:
        with connect(db_path) as conn, transaction(conn):
            cur = conn.execute("UPDATE tickets SET assignee_id=?,updated_at=? WHERE ticket_id=? AND assignee_id IS NULL AND status IN (?,?,?)",
                               (actor.id, _now(), ticket_id, *(status.value for status in LIVE_STATUSES)))
            if cur.rowcount != 1:
                raise TicketError("Another worker has already claimed this task.")
            _event(conn, ticket_id, actor.id, "worker", "assignment", f"claimed by {actor.name}")
    except sqlite3.Error as e:
        raise TicketError("The task could not be claimed.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.assignee_id != actor.id:
        raise TicketError("The task claim could not be verified.")
    return back


def create_ticket(analysis: AnalysisResult, description: str, location: str | None, ai_mode: str,
                  duplicate_of: str | None = None, is_sample: bool = False, reporter_id: int | None = None,
                  db_path: str | None = None, location_id: str | None = None, is_anonymous: bool = False,
                  critical_alert: bool = False) -> CreatedTicket:
    description = (description or "").strip()
    if not description:
        raise TicketError("A description is required.")
    raw = secrets.token_hex(4).upper()
    code, now, year = f"{raw[:4]}-{raw[4:]}", _now(), datetime.now(timezone.utc).year
    settings = get_settings()
    hours = {Priority.HIGH: settings.sla_high_hours, Priority.MEDIUM: settings.sla_medium_hours,
             Priority.LOW: settings.sla_low_hours}[analysis.priority]
    deadline = datetime.fromisoformat(now) + (timedelta(minutes=settings.sla_critical_minutes) if critical_alert else timedelta(hours=hours))
    deadline_at = deadline.isoformat(timespec="seconds")
    try:
        with connect(db_path) as c, transaction(c):
            last = c.execute("SELECT ticket_id FROM tickets WHERE ticket_id LIKE ? ORDER BY ticket_id DESC LIMIT 1", (f"RAI-{year}-%",)).fetchone()
            tid = f"RAI-{year}-{(int(last[0][-4:]) + 1) if last else 1:04d}"
            if location_id:
                known = c.execute("SELECT display_name FROM campus_locations WHERE location_id=?", (location_id,)).fetchone()
                if not known:
                    raise TicketError("Choose a valid campus location or enter it as a custom location.")
            c.execute("INSERT INTO tickets (ticket_id, description, summary, category, priority, department, status, location, location_id, "
                      "duplicate_of, review_required, ai_mode, tracking_hash, created_at, updated_at, is_sample, reporter_id, is_anonymous, critical_alert, deadline_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (tid, description, analysis.summary, analysis.category.value, analysis.priority.value,
                       SAFETY_DEPARTMENT if critical_alert else analysis.department,
                       Status.OPEN.value, (location or "").strip() or None, location_id, duplicate_of, int(analysis.review_required or critical_alert),
                       ai_mode, _hash(code), now, now, int(is_sample), reporter_id, int(is_anonymous), int(critical_alert), deadline_at))
            _event(c, tid, reporter_id, "student" if reporter_id else "system", "created",
                   f"{analysis.category.value}, {analysis.priority.value}; resolution target {deadline_at} UTC" + (f", linked to {duplicate_of}" if duplicate_of else ""))
    except sqlite3.Error as e:
        raise TicketError("The ticket could not be saved. No reference was issued.") from e
    saved = get_ticket(tid, db_path)  # verify by reading back
    if not saved or saved.description != description or saved.status != Status.OPEN:
        raise TicketError("The ticket could not be verified after saving. No reference was issued.")
    return CreatedTicket(ticket=saved, tracking_code=code)


def update_status(ticket_id: str, new_status: Status, resolution_note: str | None = None, *, actor: User, db_path=None) -> TicketRecord:
    """Staff moves: Open/Reopened -> In Progress, and Open/In Progress/Reopened -> Pending Sign-off (the fix, which needs a note).
    Closing a ticket is the student's decision (see student_signoff) or a timed close (close_unconfirmed)."""
    t = get_ticket(ticket_id, db_path)
    if not t:
        raise TicketError("Ticket not found.")
    if actor is not None and is_staff(actor.id, db_path):
        pass
    else:
        _require_assigned_worker(actor, t, db_path)
    if new_status not in ALLOWED_TRANSITIONS[t.status]:
        raise TicketError(f"Cannot move a ticket from {t.status.value} to {new_status.value}.")
    note = (resolution_note or "").strip() or None
    if new_status == Status.PENDING and (not note or len(note) < 10):
        raise TicketError("Describe what was done (at least 10 characters) so the student can verify the fix.")
    try:
        with connect(db_path) as c, transaction(c):
            if new_status == Status.PENDING:
                c.execute("UPDATE tickets SET status=?, resolution_note=?, fixed_at=?, updated_at=? WHERE ticket_id=?", (new_status.value, note, _now(), _now(), ticket_id))
            else:
                c.execute("UPDATE tickets SET status=?, updated_at=? WHERE ticket_id=?", (new_status.value, _now(), ticket_id))
            _event(c, ticket_id, actor.id, actor.role, "status", f"{t.status.value} → {new_status.value}" + (f". Fix: {note}" if new_status == Status.PENDING else ""))
    except sqlite3.Error as e:
        raise TicketError("The update could not be saved.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.status != new_status:
        raise TicketError("The update could not be verified. Nothing was changed.")
    return back


def mark_fixed(ticket_id: str, note: str, *, actor: User, db_path=None) -> TicketRecord:
    return update_status(ticket_id, Status.PENDING, note, actor=actor, db_path=db_path)


def _close(ticket_id: str, by: str, who: User, role: str, detail: str, db_path, rating: int | None = None) -> TicketRecord:
    try:
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE tickets SET status=?, resolved_at=?, resolved_by=?, rating=COALESCE(?, rating), updated_at=? WHERE ticket_id=?",
                      (Status.RESOLVED.value, _now(), by, rating, _now(), ticket_id))
            _event(c, ticket_id, who.id, role, "status", detail)
    except sqlite3.Error as e:
        raise TicketError("The ticket could not be closed.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.status != Status.RESOLVED:
        raise TicketError("The ticket could not be verified as closed. Nothing was changed.")
    return back


def close_unconfirmed(ticket_id: str, *, actor: User, db_path=None) -> TicketRecord:
    """Staff may close a fix the student never answered, but only after SIGNOFF_DAYS."""
    _require_staff(actor, db_path)
    t = get_ticket(ticket_id, db_path)
    if not t or t.status != Status.PENDING or not t.fixed_at:
        raise TicketError("This ticket is not waiting for a student's confirmation.")
    days = get_settings().signoff_days
    waited = (datetime.now(timezone.utc) - t.fixed_at).total_seconds() / 86400
    if waited < days:
        raise TicketError(f"The student has {days - waited:.1f} more day(s) to confirm. Tickets can be closed without a response after {days:g} days.")
    return _close(ticket_id, "staff_timeout", actor, "staff", f"Pending Sign-off → Resolved. Closed by staff: no response from the student after {days:g} days", db_path)


def _require_owner(actor: User | None, t: TicketRecord | None, db_path=None) -> TicketRecord:
    if actor is None or t is None or t.reporter_id != actor.id or not is_student(actor.id, db_path):
        raise TicketError("Only the student who filed this report can do this.")
    return t


def student_signoff(ticket_id: str, *, actor: User, confirm: bool, comment: str | None = None, rating: int | None = None, db_path=None) -> TicketRecord:
    """The student's half of the handshake: confirm the fix (closes the ticket) or say it is not fixed (reopens it, reason required)."""
    t = _require_owner(actor, get_ticket(ticket_id, db_path), db_path)
    if t.status != Status.PENDING:
        raise TicketError("This ticket is not waiting for your confirmation.")
    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise TicketError("Please keep your comment under 1000 characters.")
    if rating is not None and rating not in (1, 2, 3, 4, 5):
        raise TicketError("The rating must be between 1 and 5.")
    if confirm:
        back = _close(ticket_id, "student", actor, "student", "Pending Sign-off → Resolved. The student confirmed the fix" + (f" ({rating}/5)" if rating else ""), db_path, rating)
    else:
        if len(comment) < 10:
            raise TicketError("Please tell the team what is still wrong (at least 10 characters).")
        try:
            with connect(db_path) as c, transaction(c):
                c.execute("UPDATE tickets SET status=?, fixed_at=NULL, reopen_count=reopen_count+1, updated_at=? WHERE ticket_id=?", (Status.REOPENED.value, _now(), ticket_id))
                _event(c, ticket_id, actor.id, "student", "status", f"Pending Sign-off → Reopened. Not fixed: {comment}")
        except sqlite3.Error as e:
            raise TicketError("The ticket could not be reopened.") from e
        back = get_ticket(ticket_id, db_path)
        if not back or back.status != Status.REOPENED:
            raise TicketError("The ticket could not be verified as reopened.")
    if comment:
        _student_comment(ticket_id, comment, actor, db_path)
    return back


def student_resolve(ticket_id: str, note: str | None = None, *, actor: User, db_path=None) -> TicketRecord:
    """A student can close their own report at any point, for example when the problem fixed itself."""
    t = _require_owner(actor, get_ticket(ticket_id, db_path), db_path)
    if t.status == Status.RESOLVED:
        raise TicketError("This ticket is already resolved.")
    if t.status == Status.WITHDRAWN:
        raise TicketError("This ticket has been withdrawn.")
    note = (note or "").strip()[:500]
    return _close(ticket_id, "student", actor, "student", "Resolved by the student" + (f": {note}" if note else ""), db_path)


def _student_comment(ticket_id: str, body: str, actor: User, db_path=None) -> None:
    try:
        with connect(db_path) as c, transaction(c):
            c.execute("INSERT INTO ticket_comments (ticket_id, author_id, visibility, body, created_at) VALUES (?,?,?,?,?)", (ticket_id, actor.id, "public", body, _now()))
            c.execute("UPDATE tickets SET updated_at = ? WHERE ticket_id = ?", (_now(), ticket_id))
            _event(c, ticket_id, actor.id, "student", "note", "student comment")
    except sqlite3.Error as e:
        raise TicketError("Your comment could not be saved.") from e


def add_student_comment(ticket_id: str, body: str, *, actor: User, db_path=None) -> None:
    t = _require_owner(actor, get_ticket(ticket_id, db_path), db_path)
    body = (body or "").strip()
    if not 1 <= len(body) <= 1000:
        raise TicketError("A comment must be between 1 and 1000 characters.")
    if t.status in (Status.RESOLVED, Status.WITHDRAWN):
        raise TicketError("This ticket is closed. File a new report if the problem returns.")
    _student_comment(ticket_id, body, actor, db_path)


def student_timeline(ticket_id: str, *, actor: User, db_path=None) -> list[dict]:
    """What a student may see: creation, assignment and status changes, public staff notes, and their own comments. Never internal notes."""
    ticket = _require_owner(actor, get_ticket(ticket_id, db_path), db_path)
    items = []
    with connect(db_path) as c:
        for r in c.execute("SELECT e.created_at, e.actor_role, e.action, e.detail, u.name FROM ticket_events e LEFT JOIN users u ON u.id = e.actor_id "
                           "WHERE e.ticket_id = ? AND e.action IN ('created','status','assignment','withdrawn','staff_removed','deadline') ORDER BY e.id", (ticket_id,)):
            created_text = "Report received and routed"
            if ticket.deadline_at:
                created_text += f". Resolution target: {ticket.deadline_at:%d %b %Y %H:%M UTC}"
            items.append({"at": r["created_at"], "who": "ResolveAI" if r["action"] == "created" and r["actor_role"] != "staff" else (r["name"] or r["actor_role"]), "kind": "event",
                          "text": {"created": created_text, "status": r["detail"] or "Status changed", "assignment": r["detail"] or "Assignment changed", "withdrawn": r["detail"] or "Report withdrawn", "staff_removed": r["detail"] or "Ticket removed by staff", "deadline": r["detail"] or "Resolution deadline updated"}[r["action"]]})
        for r in c.execute("SELECT m.created_at, m.body, u.name, u.role FROM ticket_comments m LEFT JOIN users u ON u.id = m.author_id WHERE m.ticket_id = ? AND m.visibility = 'public' ORDER BY m.id", (ticket_id,)):
            items.append({"at": r["created_at"], "who": r["name"] or "staff", "kind": "student" if r["role"] == "student" else "staff", "text": r["body"]})
    return sorted(items, key=lambda i: i["at"])


def correct_fields(ticket_id: str, category: Category, priority: Priority, department: str, *, actor: User, db_path=None) -> TicketRecord:
    _require_staff(actor, db_path)
    if department not in DEPARTMENTS:
        raise TicketError("Unknown department.")
    old = get_ticket(ticket_id, db_path)
    if not old:
        raise TicketError("Ticket not found.")
    changes = [f"{n}: {a} → {b}" for n, a, b in (("category", old.category.value, category.value), ("priority", old.priority.value, priority.value),
                                                ("department", old.department, department)) if a != b]
    try:
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE tickets SET category=?, priority=?, department=?, updated_at=? WHERE ticket_id=?",
                      (category.value, priority.value, department, _now(), ticket_id))
            if changes:
                _event(c, ticket_id, actor.id, "staff", "correction", "; ".join(changes))
    except sqlite3.Error as e:
        raise TicketError("The correction could not be saved.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or (back.category, back.priority, back.department) != (category, priority, department):
        raise TicketError("The correction could not be verified. Nothing was changed.")
    return back


def update_ticket_details(ticket_id: str, summary: str, description: str, location: str | None, *, actor: User, db_path=None) -> TicketRecord:
    """Staff may correct the report text, short summary, and location without changing AI triage fields."""
    _require_staff(actor, db_path)
    description = (description or "").strip()
    summary = (summary or "").strip()
    location = (location or "").strip() or None
    if not description or len(description) > 5000:
        raise TicketError("Description must be between 1 and 5000 characters.")
    if not summary or len(summary) > 240:
        raise TicketError("Summary must be between 1 and 240 characters.")
    if location and len(location) > 200:
        raise TicketError("Location must be 200 characters or fewer.")
    old = get_ticket(ticket_id, db_path)
    if not old:
        raise TicketError("Ticket not found.")
    try:
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE tickets SET summary=?, description=?, location=?, updated_at=? WHERE ticket_id=?", (summary, description, location, _now(), ticket_id))
            _event(c, ticket_id, actor.id, "staff", "edit", "Report summary, description, or location corrected")
    except sqlite3.Error as e:
        raise TicketError("The ticket details could not be saved.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or (back.summary, back.description, back.location) != (summary, description, location):
        raise TicketError("The ticket details could not be verified.")
    return back


def update_deadline(ticket_id: str, new_deadline: datetime, reason: str = "", *, actor: User, db_path=None) -> TicketRecord:
    """Change a live ticket's resolution target; extensions require a student-visible reason."""
    _require_staff(actor, db_path)
    t = get_ticket(ticket_id, db_path)
    if not t:
        raise TicketError("Ticket not found.")
    if t.staff_removed or t.status not in (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED):
        raise TicketError("Only active tickets can have their resolution deadline changed.")
    if not isinstance(new_deadline, datetime) or new_deadline.tzinfo is None:
        raise TicketError("Choose a valid deadline in UTC.")
    new_deadline = new_deadline.astimezone(timezone.utc).replace(microsecond=0)
    if new_deadline <= datetime.now(timezone.utc):
        raise TicketError("The new deadline must be in the future.")
    reason = " ".join((reason or "").split())
    if len(reason) > 500:
        raise TicketError("The reason must be 500 characters or fewer.")
    settings = get_settings()
    default_hours = {Priority.HIGH: settings.sla_high_hours, Priority.MEDIUM: settings.sla_medium_hours,
                     Priority.LOW: settings.sla_low_hours}[t.priority]
    old_deadline = t.deadline_at or (t.created_at + timedelta(hours=default_hours))
    if old_deadline.tzinfo is None:
        old_deadline = old_deadline.replace(tzinfo=timezone.utc)
    old_deadline = old_deadline.astimezone(timezone.utc).replace(microsecond=0)
    if new_deadline == old_deadline:
        raise TicketError("The selected deadline is unchanged.")
    extending = new_deadline > old_deadline
    if extending and not 5 <= len(reason) <= 500:
        raise TicketError("A reason of at least 5 characters is required to extend the deadline.")
    old_label = old_deadline.strftime("%d %b %Y %H:%M UTC")
    new_label = new_deadline.strftime("%d %b %Y %H:%M UTC")
    detail = f"Resolution target {'extended' if extending else 'changed'} from {old_label} to {new_label}."
    if reason:
        detail += f" Reason: {reason}"
    try:
        with connect(db_path) as c, transaction(c):
            cur = c.execute("UPDATE tickets SET deadline_at=?, updated_at=? WHERE ticket_id=? AND status IN (?,?,?) AND staff_removed=0",
                            (new_deadline.isoformat(timespec="seconds"), _now(), ticket_id,
                             Status.OPEN.value, Status.IN_PROGRESS.value, Status.REOPENED.value))
            if cur.rowcount != 1:
                raise TicketError("This ticket is no longer active; refresh and try again.")
            _event(c, ticket_id, actor.id, "staff", "deadline", detail)
    except sqlite3.Error as e:
        raise TicketError("The resolution deadline could not be updated.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.deadline_at != new_deadline:
        raise TicketError("The resolution deadline update could not be verified.")
    return back


def delete_ticket(ticket_id: str, reason: str, *, actor: User, db_path=None) -> TicketRecord:
    """Remove a ticket from active work while preserving its record and notifying its reporter."""
    _require_staff(actor, db_path)
    reason = " ".join((reason or "").split())
    if not 5 <= len(reason) <= 500:
        raise TicketError("Give a removal reason between 5 and 500 characters.")
    old = get_ticket(ticket_id, db_path)
    if not old:
        raise TicketError("Ticket not found.")
    if old.staff_removed:
        raise TicketError("This ticket has already been removed from active work.")
    try:
        with connect(db_path) as c, transaction(c):
            cur = c.execute("UPDATE tickets SET status=?, staff_removed=1, staff_removal_reason=?, withdrawal_review=0, updated_at=? "
                            "WHERE ticket_id=? AND staff_removed=0",
                            (Status.WITHDRAWN.value, reason, _now(), ticket_id))
            if cur.rowcount != 1:
                raise TicketError("This ticket has already been removed from active work.")
            _event(c, ticket_id, actor.id, "staff", "staff_removed",
                   f"Ticket removed from active work by staff. Reason: {reason}")
    except sqlite3.Error as e:
        raise TicketError("The ticket could not be removed from active work.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or not back.staff_removed or back.staff_removal_reason != reason:
        raise TicketError("The ticket removal could not be verified.")
    return back


def withdraw_ticket(ticket_id: str, reason: str, *, actor: User, db_path=None) -> TicketRecord:
    """Soft-withdraw the reporter's own new, unassigned ticket and preserve its full audit history."""
    t = _require_owner(actor, get_ticket(ticket_id, db_path), db_path)
    if t.status != Status.OPEN or t.assignee_id is not None:
        raise TicketError("You can withdraw a report only while it is open and unassigned.")
    if reason not in WITHDRAWAL_REASONS:
        raise TicketError("Choose a reason for withdrawing this report.")
    now = datetime.now(timezone.utc)
    created = t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)
    if now - created > timedelta(minutes=WITHDRAWAL_WINDOW_MINUTES):
        raise TicketError(f"Reports can be withdrawn only within {WITHDRAWAL_WINDOW_MINUTES} minutes of submission.")
    try:
        with connect(db_path) as c, transaction(c):
            current = c.execute("SELECT reporter_id, status, assignee_id, created_at FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
            if not current or current["reporter_id"] != actor.id:
                raise TicketError("Only the student who filed this report can do this.")
            if current["status"] != Status.OPEN.value or current["assignee_id"] is not None:
                raise TicketError("You can withdraw a report only while it is open and unassigned.")
            db_created = datetime.fromisoformat(current["created_at"])
            if db_created.tzinfo is None:
                db_created = db_created.replace(tzinfo=timezone.utc)
            if now - db_created > timedelta(minutes=WITHDRAWAL_WINDOW_MINUTES):
                raise TicketError(f"Reports can be withdrawn only within {WITHDRAWAL_WINDOW_MINUTES} minutes of submission.")
            since = (now - timedelta(days=7)).isoformat(timespec="seconds")
            count = c.execute("SELECT COUNT(*) FROM ticket_events WHERE actor_id=? AND actor_role='student' AND action='withdrawn' AND created_at>=?", (actor.id, since)).fetchone()[0]
            flagged = count + 1 >= WITHDRAWAL_REVIEW_THRESHOLD
            c.execute("UPDATE tickets SET status=?, withdrawal_review=?, withdrawal_reason=?, updated_at=? WHERE ticket_id=? AND reporter_id=?",
                      (Status.WITHDRAWN.value, int(flagged), reason, now.isoformat(timespec="seconds"), ticket_id, actor.id))
            detail = f"Report withdrawn by student. Reason: {reason}."
            if flagged:
                detail += " Repeated withdrawals within 7 days; staff review requested."
            _event(c, ticket_id, actor.id, "student", "withdrawn", detail)
    except sqlite3.Error as e:
        raise TicketError("The report could not be withdrawn.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.status != Status.WITHDRAWN or back.withdrawal_review != flagged:
        raise TicketError("The report withdrawal could not be verified.")
    return back


def set_duplicate_link(ticket_id: str, parent_id: str | None, *, actor: User, db_path=None) -> TicketRecord:
    _require_staff(actor, db_path)
    old = get_ticket(ticket_id, db_path)
    if not old or parent_id == ticket_id or (parent_id and not get_ticket(parent_id, db_path)):
        raise TicketError("Invalid parent ticket.")
    try:
        with connect(db_path) as c, transaction(c):
            c.execute("UPDATE tickets SET duplicate_of=?, updated_at=? WHERE ticket_id=?", (parent_id, _now(), ticket_id))
            _event(c, ticket_id, actor.id, "staff", "link", f"linked to {parent_id}" if parent_id else f"link to {old.duplicate_of} removed")
    except sqlite3.Error as e:
        raise TicketError("The link could not be saved.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.duplicate_of != parent_id:
        raise TicketError("The link could not be verified.")
    return back


def get_events(ticket_id: str, *, actor: User, db_path=None) -> list[dict]:
    _require_staff(actor, db_path)
    ticket = get_ticket(ticket_id, db_path)
    if not ticket:
        raise TicketError("Ticket not found.")
    with connect(db_path) as c:
        rows = c.execute("SELECT e.created_at, e.actor_role, e.action, e.detail, u.name FROM ticket_events e LEFT JOIN users u ON u.id = e.actor_id "
                         "WHERE e.ticket_id = ? ORDER BY e.id", (ticket_id,)).fetchall()
    return [{"at": r["created_at"], "who": ("Anonymous student" if ticket.is_anonymous and r["actor_role"] == "student" else r["name"] or r["actor_role"]), "role": r["actor_role"], "action": r["action"], "detail": r["detail"]} for r in rows]


def get_public_status(ticket_id: str, tracking_code: str, db_path=None) -> PublicStatus | None:
    """Guests need the ID and tracking code. Failed attempts are counted per ticket in the database and lock lookups."""
    key = (ticket_id or "").strip().upper()
    if not _ID.match(key):
        return None
    now = datetime.now(timezone.utc)
    with connect(db_path) as c:
        lk = c.execute("SELECT failed, locked_until FROM lookup_attempts WHERE ticket_key = ?", (key,)).fetchone()
        row = c.execute("SELECT tracking_hash FROM tickets WHERE ticket_id = ?", (key,)).fetchone()
    if lk and lk["locked_until"] and datetime.fromisoformat(lk["locked_until"]) > now:
        raise TicketError(f"Too many unsuccessful attempts for this ticket. Please try again in {LOOKUP_LOCK_MIN} minutes.")
    if not row or not hmac.compare_digest(row[0], _hash(tracking_code or "")):
        fails = (lk["failed"] if lk else 0) + 1
        lock = (now + timedelta(minutes=LOOKUP_LOCK_MIN)).isoformat(timespec="seconds") if fails >= LOOKUP_MAX else None
        with connect(db_path) as c, transaction(c):
            c.execute("INSERT INTO lookup_attempts (ticket_key, failed, locked_until) VALUES (?,?,?) "
                      "ON CONFLICT(ticket_key) DO UPDATE SET failed=excluded.failed, locked_until=excluded.locked_until", (key, 0 if lock else fails, lock))
        return None
    if lk:
        with connect(db_path) as c, transaction(c):
            c.execute("DELETE FROM lookup_attempts WHERE ticket_key = ?", (key,))
    t = get_ticket(key, db_path)
    updates = _public_updates(key, db_path) + _public_deadline_updates(key, db_path)
    return PublicStatus(**t.model_dump(include=set(PublicStatus.model_fields) - {"updates"}),
                        updates=sorted(updates, key=lambda item: item["at"]))


# ---------------------------------------------------------------- workspace: assignment, notes, timeline, bulk
def _public_updates(ticket_id: str, db_path=None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute("SELECT created_at, body FROM ticket_comments WHERE ticket_id = ? AND visibility = 'public' ORDER BY id", (ticket_id,)).fetchall()
    return [{"at": r["created_at"], "text": r["body"]} for r in rows]


def _public_deadline_updates(ticket_id: str, db_path=None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute("SELECT created_at, detail FROM ticket_events WHERE ticket_id=? AND action='deadline' ORDER BY id", (ticket_id,)).fetchall()
    return [{"at": r["created_at"], "text": r["detail"] or "Resolution deadline updated"} for r in rows]


def latest_public_updates(ticket_ids: list[str], db_path=None) -> dict[str, str]:
    """Only public notes. Callers pass IDs the signed-in student owns."""
    out = {}
    for tid in ticket_ids:
        ups = _public_updates(tid, db_path)
        if ups:
            out[tid] = ups[-1]["text"]
    return out


def list_staff(*, actor: User, db_path=None) -> list[User]:
    _require_staff(actor, db_path)
    with connect(db_path) as c:
        return [User(id=r["id"], name=r["name"], email=r["email"], role=r["role"], department=r["department"]) for r in c.execute("SELECT id, name, email, role, department FROM users WHERE role IN ('staff','worker') AND is_active=1 ORDER BY name")]


def assign_ticket(ticket_id: str, assignee_id: int | None, *, actor: User, db_path=None) -> TicketRecord:
    _require_staff(actor, db_path)
    t = get_ticket(ticket_id, db_path)
    if not t:
        raise TicketError("Ticket not found.")
    if t.status == Status.WITHDRAWN:
        raise TicketError("Withdrawn reports cannot be assigned.")
    if assignee_id is not None and not is_staff_or_worker(assignee_id, db_path):
        raise TicketError("Tickets can only be assigned to staff admins or worker accounts.")
    try:
        with connect(db_path) as c, transaction(c):
            current = c.execute("SELECT status FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
            if not current:
                raise TicketError("Ticket not found.")
            if current["status"] == Status.WITHDRAWN.value:
                raise TicketError("Withdrawn reports cannot be assigned.")
            name = None
            if assignee_id is not None:
                name = c.execute("SELECT name FROM users WHERE id = ?", (assignee_id,)).fetchone()["name"]
            c.execute("UPDATE tickets SET assignee_id = ?, updated_at = ? WHERE ticket_id = ?", (assignee_id, _now(), ticket_id))
            _event(c, ticket_id, actor.id, "staff", "assignment", f"assigned to {name}" if name else "unassigned")
    except sqlite3.Error as e:
        raise TicketError("The assignment could not be saved.") from e
    back = get_ticket(ticket_id, db_path)
    if not back or back.assignee_id != assignee_id:
        raise TicketError("The assignment could not be verified.")
    return back


def add_comment(ticket_id: str, body: str, visibility: str, *, actor: User, db_path=None) -> None:
    """'internal' notes are staff-only. 'public' notes are shown to the student who filed the report."""
    ticket = get_ticket(ticket_id, db_path)
    if not ticket:
        raise TicketError("Ticket not found.")
    if actor is not None and is_staff(actor.id, db_path):
        pass
    else:
        _require_assigned_worker(actor, ticket, db_path)
        if visibility != "public":
            raise TicketError("Workers can send updates visible to the student and staff only.")
    body = (body or "").strip()
    if visibility not in ("internal", "public"):
        raise TicketError("Choose who can see this note.")
    if not 1 <= len(body) <= 1000:
        raise TicketError("A note must be between 1 and 1000 characters.")
    try:
        with connect(db_path) as c, transaction(c):
            cur = c.execute("INSERT INTO ticket_comments (ticket_id, author_id, visibility, body, created_at) VALUES (?,?,?,?,?)", (ticket_id, actor.id, visibility, body, _now()))
            c.execute("UPDATE tickets SET updated_at = ? WHERE ticket_id = ?", (_now(), ticket_id))
            _event(c, ticket_id, actor.id, actor.role, "note", f"{visibility} note added")
            cid = cur.lastrowid
        with connect(db_path) as c:
            if not c.execute("SELECT 1 FROM ticket_comments WHERE id = ? AND body = ?", (cid, body)).fetchone():
                raise TicketError("The note could not be verified.")
    except sqlite3.Error as e:
        raise TicketError("The note could not be saved.") from e


def get_timeline(ticket_id: str, *, actor: User, db_path=None) -> list[dict]:
    """Audit events and notes in one list, oldest first."""
    _require_staff(actor, db_path)
    items = [{"at": e["at"], "who": e["who"], "kind": "event", "text": f"{e['action']}" + (f": {e['detail']}" if e["detail"] else "")} for e in get_events(ticket_id, actor=actor, db_path=db_path)
             if e["action"] != "note"]
    with connect(db_path) as c:
        for r in c.execute("SELECT m.created_at, m.visibility, m.body, u.name, u.role, t.is_anonymous FROM ticket_comments m LEFT JOIN users u ON u.id = m.author_id JOIN tickets t ON t.ticket_id=m.ticket_id WHERE m.ticket_id = ? ORDER BY m.id", (ticket_id,)):
            who = "Anonymous student" if r["is_anonymous"] and r["role"] == "student" else r["name"] or "staff"
            items.append({"at": r["created_at"], "who": who, "kind": "student" if r["role"] == "student" else "public" if r["visibility"] == "public" else "internal", "text": r["body"]})
    return sorted(items, key=lambda i: i["at"])


def get_worker_timeline(ticket_id: str, *, actor: User, db_path=None) -> list[dict]:
    """Assigned workers see public updates and task events, never staff-only notes."""
    ticket = get_ticket(ticket_id, db_path)
    _require_assigned_worker(actor, ticket, db_path)
    items = []
    with connect(db_path) as conn:
        for r in conn.execute("SELECT e.created_at,e.actor_role,e.action,e.detail,u.name FROM ticket_events e LEFT JOIN users u ON u.id=e.actor_id "
                              "WHERE e.ticket_id=? AND e.action IN ('created','status','assignment','deadline') ORDER BY e.id", (ticket_id,)):
            who = "Anonymous student" if ticket.is_anonymous and r["actor_role"] == "student" else r["name"] or r["actor_role"]
            items.append({"at": r["created_at"], "who": who, "kind": "event", "text": r["detail"] or r["action"]})
        for r in conn.execute("SELECT m.created_at,m.body,m.visibility,u.name,u.role FROM ticket_comments m LEFT JOIN users u ON u.id=m.author_id "
                              "WHERE m.ticket_id=? AND m.visibility='public' ORDER BY m.id", (ticket_id,)):
            who = "Anonymous student" if ticket.is_anonymous and r["role"] == "student" else r["name"] or "staff"
            items.append({"at": r["created_at"], "who": who, "kind": r["role"], "text": r["body"]})
    return sorted(items, key=lambda item: item["at"])


def bulk_assign(ticket_ids: list[str], assignee_id: int | None, *, actor: User, db_path=None) -> tuple[list[str], dict[str, str]]:
    _require_staff(actor, db_path)
    ok, failed = [], {}
    for tid in ticket_ids:
        try:
            assign_ticket(tid, assignee_id, actor=actor, db_path=db_path)
            ok.append(tid)
        except TicketError as e:
            failed[tid] = str(e)
    return ok, failed


def bulk_status(ticket_ids: list[str], new_status: Status, *, actor: User, db_path=None) -> tuple[list[str], dict[str, str]]:
    _require_staff(actor, db_path)
    ok, failed = [], {}
    for tid in ticket_ids:
        try:
            update_status(tid, new_status, actor=actor, db_path=db_path)
            ok.append(tid)
        except TicketError as e:
            failed[tid] = str(e)
    return ok, failed
