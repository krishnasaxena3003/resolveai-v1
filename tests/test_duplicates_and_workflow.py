import json
import pytest
from duplicate_service import DEFAULT_THRESHOLD, find_candidates, similarity
from ticket_service import create_ticket, list_tickets
from conftest import force_status
from ai_service import fallback_analysis
from schemas import Status
from workflow import InputError, finalize_submission, prepare_submission
from conftest import FakeClient

GOOD = json.dumps({"summary": "Outage in Hostel Block B", "category": "Electricity", "priority": "High"})


def seed(db, text, loc="Hostel Block B"):
    return create_ticket(fallback_analysis(text), text, loc, "fallback", db_path=db).ticket


def test_similar_report_is_a_candidate_unrelated_is_not(db):
    seed(db, "No electricity in Hostel Block B since morning")
    ex = list_tickets(db_path=db)
    assert find_candidates("Power cut, no electricity in Hostel Block B", "Hostel Block B", ex, DEFAULT_THRESHOLD)
    assert not find_candidates("Projector not working in lecture hall 2", "LH-2", ex, DEFAULT_THRESHOLD)


def test_resolved_tickets_are_not_candidates(db):
    t = seed(db, "No electricity in Hostel Block B since morning")
    force_status(db, t.ticket_id, Status.RESOLVED)
    assert not find_candidates("No electricity in Hostel Block B", "Hostel Block B", list_tickets(db_path=db), DEFAULT_THRESHOLD)


def test_different_location_lowers_score():
    a = similarity("no electricity in block", "Hostel Block B", "no electricity in block", "Library")
    assert a < 100


def test_short_input_rejected_no_ticket(db):
    with pytest.raises(InputError):
        prepare_submission("help", db_path=db)
    assert list_tickets(db_path=db) == []


def test_full_flow_new_ticket(db):
    p = prepare_submission("No electricity in Hostel Block B since morning", "Hostel Block B", client=FakeClient([GOOD]), db_path=db)
    assert p.outcome.mode == "llm" and p.candidates == []
    c = finalize_submission(p, db_path=db)
    assert c.ticket.ticket_id.startswith("RAI-") and c.ticket.duplicate_of is None


def test_full_flow_duplicate_is_linked_not_discarded(db):
    first = seed(db, "No electricity in Hostel Block B since morning")
    p = prepare_submission("Power cut, no electricity in Hostel Block B", "Hostel Block B", client=FakeClient([GOOD]), db_path=db)
    assert p.candidates and p.candidates[0].ticket_id == first.ticket_id
    c = finalize_submission(p, link_to=first.ticket_id, db_path=db)
    assert c.ticket.duplicate_of == first.ticket_id and len(list_tickets(db_path=db)) == 2


def test_ai_outage_still_creates_flagged_ticket(db):
    p = prepare_submission("No electricity in Hostel Block B since morning", client=FakeClient([TimeoutError()]), db_path=db)
    c = finalize_submission(p, db_path=db)
    assert c.ticket.ai_mode == "fallback" and c.ticket.review_required


def test_shipped_matcher_regression_guard():
    """Not a quality claim. Fails if a change makes the matcher clearly worse on the labelled pairs."""
    from eval_duplicates import DATA, SCORERS, metrics
    m = metrics(SCORERS["dice_issue_words+place_penalty"], DATA, DEFAULT_THRESHOLD)
    assert m["recall"] >= 0.55 and m["precision"] >= 0.75


def test_ai_eval_runs_offline_on_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    import eval_ai
    r = eval_ai.run()
    assert r["mode"] == "fallback-rules" and r["n"] >= 30 and r["llm_structured_output_rate"] == 0
