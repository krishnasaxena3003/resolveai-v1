"""Occupation-scoped worker accounts and task access."""
import pytest

from ai_service import fallback_analysis
from auth_service import AuthError, authenticate, create_worker, register_student
from schemas import Status
from ticket_service import (TicketError, add_comment, assign_ticket, claim_worker_task,
                            create_ticket, get_ticket, worker_list_tasks, update_status)


def _ticket(db, description):
    return create_ticket(fallback_analysis(description), description, "Engineering Block", "fallback", db_path=db).ticket


def test_worker_signin_requires_the_provisioned_occupation(db):
    worker = create_worker("Electrical Worker", "worker@campus.edu", "worker-password-1",
                           "Electrical Maintenance", db_path=db)
    signed_in = authenticate(worker.email, "worker-password-1", role="worker",
                             occupation="Electrical Maintenance", db_path=db)
    assert signed_in.role == "worker" and signed_in.department == "Electrical Maintenance"
    with pytest.raises(AuthError, match="Incorrect email or password"):
        authenticate(worker.email, "worker-password-1", role="worker",
                     occupation="Plumbing", db_path=db)
    with pytest.raises(AuthError, match="Incorrect email or password"):
        authenticate(worker.email, "worker-password-1", role="worker", db_path=db)


def test_worker_can_only_claim_team_tasks_and_post_public_updates(db):
    worker = create_worker("Electrical Worker", "worker@campus.edu", "worker-password-1",
                           "Electrical Maintenance", db_path=db)
    student = register_student("Student", "student@campus.edu", "student-password-1", db_path=db)
    same_team = _ticket(db, "Power outage in the engineering corridor")
    other_team = _ticket(db, "Water pipe leaking in the library washroom")
    before = worker_list_tasks(actor=worker, db_path=db)
    assert same_team.ticket_id in {t.ticket_id for t in before}
    assert other_team.ticket_id not in {t.ticket_id for t in before}

    claim_worker_task(same_team.ticket_id, actor=worker, db_path=db)
    with pytest.raises(TicketError, match="not available to your occupation"):
        claim_worker_task(other_team.ticket_id, actor=worker, db_path=db)
    with pytest.raises(TicketError, match="visible to the student and staff"):
        add_comment(same_team.ticket_id, "Internal note", "internal", actor=worker, db_path=db)
    add_comment(same_team.ticket_id, "I am checking the electrical panel.", "public", actor=worker, db_path=db)
    update_status(same_team.ticket_id, Status.IN_PROGRESS, actor=worker, db_path=db)
    assert get_ticket(same_team.ticket_id, db).status == Status.IN_PROGRESS
    with pytest.raises(TicketError, match="signed-in workers"):
        worker_list_tasks(actor=student, db_path=db)


def test_staff_can_assign_worker_and_worker_cannot_edit_another_workers_ticket(db):
    from auth_service import create_staff

    staff = create_staff("Staff Admin", "staff@campus.edu", "staff-password-1", db_path=db)
    worker = create_worker("Electrical Worker", "worker@campus.edu", "worker-password-1",
                           "Electrical Maintenance", db_path=db)
    other = create_worker("Other Worker", "other@campus.edu", "other-password-1",
                          "Electrical Maintenance", db_path=db)
    ticket = _ticket(db, "Power outlet sparks in engineering corridor")
    assign_ticket(ticket.ticket_id, worker.id, actor=staff, db_path=db)
    with pytest.raises(TicketError, match="assigned to this ticket"):
        update_status(ticket.ticket_id, Status.IN_PROGRESS, actor=other, db_path=db)
