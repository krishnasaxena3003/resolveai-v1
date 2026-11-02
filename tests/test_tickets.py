import sqlite3
import pytest
from ai_service import fallback_analysis
from schemas import Category, Priority, Status
from ticket_service import (TicketError, add_comment, create_ticket, delete_ticket, get_public_status, get_ticket, list_tickets,
                            update_ticket_details)
from conftest import correct_fields, set_duplicate_link, staff_for, update_status

T = "No electricity in Hostel Block B since morning"


def make(db, text=T, **kw):
    return create_ticket(fallback_analysis(text), text, "Hostel Block B", "fallback", db_path=db, **kw)


def test_create_issues_unique_sequential_ids_and_persists(db):
    a, b = make(db), make(db, "Wi-Fi down in library")
    assert a.ticket.ticket_id.endswith("0001") and b.ticket.ticket_id.endswith("0002")
    assert a.ticket.status == Status.OPEN and len(list_tickets(db_path=db)) == 2


def test_empty_description_blocked(db):
    with pytest.raises(TicketError):
        create_ticket(fallback_analysis(T), "   ", None, "fallback", db_path=db)
    assert list_tickets(db_path=db) == []


def test_db_failure_gives_no_reference(db, monkeypatch):
    import ticket_service
    monkeypatch.setattr(ticket_service, "connect", lambda p=None: (_ for _ in ()).throw(sqlite3.OperationalError("disk")))
    with pytest.raises(TicketError, match="No reference was issued"):
        make(db)


def test_status_transitions_enforced_and_persist(db):
    t = make(db).ticket
    with pytest.raises(TicketError):
        update_status(t.ticket_id, Status.RESOLVED, db_path=db)  # staff cannot close a ticket
    with pytest.raises(TicketError, match="at least 10"):
        update_status(t.ticket_id, Status.PENDING, "short", db_path=db)  # a fix must be described
    update_status(t.ticket_id, Status.IN_PROGRESS, db_path=db)
    r = update_status(t.ticket_id, Status.PENDING, "Fuse replaced and tested", db_path=db)
    assert r.status == Status.PENDING and r.fixed_at is not None and get_ticket(t.ticket_id, db).resolution_note == "Fuse replaced and tested"
    with pytest.raises(TicketError):
        update_status(t.ticket_id, Status.IN_PROGRESS, db_path=db)  # now it is the student's move


def test_correction_validated_and_verified(db):
    t = make(db).ticket
    r = correct_fields(t.ticket_id, Category.HOSTEL, Priority.LOW, "Hostel Maintenance", db_path=db)
    assert r.category == Category.HOSTEL
    with pytest.raises(TicketError):
        correct_fields(t.ticket_id, Category.HOSTEL, Priority.LOW, "Made Up Dept", db_path=db)


def test_student_status_needs_ticket_id_and_tracking_code(db):
    c = make(db)
    ok = get_public_status(c.ticket.ticket_id, c.tracking_code.lower(), db_path=db)
    assert ok and ok.status == Status.OPEN and not hasattr(ok, "description")
    assert get_public_status(c.ticket.ticket_id, "WRONG1", db_path=db) is None
    assert get_public_status("RAI-2026-9999", c.tracking_code, db_path=db) is None


def test_tracking_code_is_not_stored_in_plain_text(db):
    c = make(db)
    with sqlite3.connect(db) as conn:
        stored = conn.execute("SELECT tracking_hash FROM tickets").fetchone()[0]
    assert c.tracking_code not in stored and len(stored) == 64


def test_duplicate_link_set_and_cleared(db):
    p, ch = make(db).ticket, make(db, "Power cut in Hostel Block B").ticket
    assert set_duplicate_link(ch.ticket_id, p.ticket_id, db_path=db).duplicate_of == p.ticket_id
    assert set_duplicate_link(ch.ticket_id, None, db_path=db).duplicate_of is None
    with pytest.raises(TicketError):
        set_duplicate_link(ch.ticket_id, ch.ticket_id, db_path=db)


def test_staff_can_edit_ticket_details_and_invalid_text_is_rejected(db):
    t = make(db).ticket
    actor = staff_for(db)
    edited = update_ticket_details(t.ticket_id, "Power issue in Block B", "Power has been out since morning.", "Block B", actor=actor, db_path=db)
    assert (edited.summary, edited.description, edited.location) == ("Power issue in Block B", "Power has been out since morning.", "Block B")
    with pytest.raises(TicketError, match="Description"):
        update_ticket_details(t.ticket_id, "Summary", "  ", "Block B", actor=actor, db_path=db)


def test_staff_removes_ticket_from_active_work_and_preserves_history(db):
    parent = make(db).ticket
    child = make(db, "Power outage in Hostel Block B").ticket
    actor = staff_for(db)
    set_duplicate_link(child.ticket_id, parent.ticket_id, db_path=db)
    add_comment(parent.ticket_id, "Internal note", "internal", actor=actor, db_path=db)
    removed = delete_ticket(parent.ticket_id, "Duplicate report; retain the original ticket.", actor=actor, db_path=db)
    assert removed.staff_removed is True
    assert removed.staff_removal_reason == "Duplicate report; retain the original ticket."
    assert get_ticket(parent.ticket_id, db_path=db).status == Status.WITHDRAWN
    assert get_ticket(child.ticket_id, db_path=db).duplicate_of == parent.ticket_id


def test_filters(db):
    make(db), make(db, "Wi-Fi down in library")
    assert len(list_tickets(category=Category.NETWORK, db_path=db)) == 1
    assert len(list_tickets(search="library", db_path=db)) == 1


def test_tracking_code_format_and_lenient_input(db):
    c = make(db)
    assert len(c.tracking_code) == 9 and c.tracking_code[4] == "-"
    assert get_public_status(c.ticket.ticket_id.lower(), " " + c.tracking_code.replace("-", "").lower() + " ", db_path=db)
