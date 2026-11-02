"""Orchestrates: validate input -> AI analysis -> duplicate search -> create (human chooses link or new)."""
from dataclasses import dataclass
from ai_service import AnalysisOutcome, analyze_complaint
from config import get_settings
from duplicate_service import find_candidates
from schemas import CreatedTicket, DuplicateCandidate, Priority, SAFETY_DEPARTMENT
from ticket_service import TicketError, create_ticket, get_ticket, list_tickets
from safety_alerts import is_critical_hazard

MIN_LEN, MAX_LEN = 15, 1000


class InputError(ValueError):
    pass


@dataclass
class Prepared:
    description: str
    location: str | None
    outcome: AnalysisOutcome
    candidates: list[DuplicateCandidate]
    location_id: str | None = None
    critical_alert: bool = False


def prepare_submission(description: str, location: str | None = None, client=None, db_path=None, location_id: str | None = None) -> Prepared:
    d, loc = (description or "").strip(), (location or "").strip() or None
    if len(d) < MIN_LEN:
        raise InputError("Please describe the problem in at least a sentence so it can be routed.")
    if len(d) > MAX_LEN or (loc and len(loc) > 80):
        raise InputError("The description or location is too long.")
    outcome = analyze_complaint(d, loc, client=client)
    critical = is_critical_hazard(d)
    if critical:
        outcome.result = outcome.result.model_copy(update={
            "priority": Priority.HIGH,
            "department": SAFETY_DEPARTMENT,
            "review_required": True,
            "rationale": "Potential life-safety hazard detected by fixed safety rules. Staff must verify immediately.",
        })
    existing = list_tickets(db_path=db_path)
    return Prepared(d, loc, outcome, find_candidates(d, loc, existing, get_settings().dup_threshold), location_id, critical)


def finalize_submission(p: Prepared, link_to: str | None = None, reporter_id: int | None = None, db_path=None,
                        is_anonymous: bool = False) -> CreatedTicket:
    """link_to is the parent ticket the person chose; None saves as a new, unlinked ticket."""
    if link_to and not get_ticket(link_to, db_path):
        raise TicketError("The ticket you chose to link to no longer exists.")
    return create_ticket(p.outcome.result, p.description, p.location, p.outcome.mode, duplicate_of=link_to, reporter_id=reporter_id,
                         db_path=db_path, location_id=p.location_id, is_anonymous=is_anonymous,
                         critical_alert=p.critical_alert)
