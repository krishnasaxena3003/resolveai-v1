import base64
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest

from ai_service import fallback_analysis
from auth_service import (AuthError, DEMO_PASSWORD, DEMO_WORKER_ACCOUNTS, authenticate, create_worker,
                          list_worker_contacts, update_worker_phone)
from conftest import staff_for
from database import connect
from safety_alerts import sms_safety_workers_critical_alert
from ticket_service import create_ticket


def test_worker_phone_validation_and_staff_only_edit(db):
    admin = staff_for(db)
    worker = create_worker("Safety One", "safety1@t.edu", "safety-password-1",
                           "Campus Safety & Emergency Response", db_path=db)
    assert list_worker_contacts(actor=admin, db_path=db)[0]["phone"] == "+916398758826"
    update_worker_phone(worker.id, " +91 (63987) 58826 ", actor=admin, db_path=db)
    assert list_worker_contacts(actor=admin, db_path=db)[0]["phone"] == "+916398758826"
    with pytest.raises(AuthError, match="international phone"):
        update_worker_phone(worker.id, "6398758826", actor=admin, db_path=db)


def test_demo_worker_account_for_every_occupation(db, monkeypatch):
    from auth_service import ensure_demo_accounts
    monkeypatch.setenv("DEMO_MODE", "1")
    assert ensure_demo_accounts(db_path=db)
    for _, email, occupation in DEMO_WORKER_ACCOUNTS:
        user = authenticate(email, DEMO_PASSWORD, role="worker", occupation=occupation, db_path=db)
        with connect(db) as conn:
            row = conn.execute("SELECT is_demo, phone FROM users WHERE id=?", (user.id,)).fetchone()
        assert row["is_demo"] == 1 and row["phone"] == "+916398758826"


def test_safety_sms_targets_unique_real_safety_worker_phones_only(db, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-test-token")
    monkeypatch.setenv("TWILIO_MESSAGING_SERVICE_SID", "MGtest")
    monkeypatch.delenv("TWILIO_FROM_PHONE", raising=False)
    real = create_worker("Safety One", "safety-real@t.edu", "safety-password-1",
                         "Campus Safety & Emergency Response", db_path=db, phone="+919999000001")
    create_worker("Safety Two", "safety-real2@t.edu", "safety-password-2",
                  "Campus Safety & Emergency Response", db_path=db, phone="+919999000001")
    create_worker("Electrician", "electrician@t.edu", "electric-password-1",
                  "Electrical Maintenance", db_path=db, phone="+919999000002")
    create_worker("Demo Safety", "safety-demo@t.edu", "safety-password-3",
                  "Campus Safety & Emergency Response", is_demo=True, db_path=db, phone="+919999000003")
    ticket = create_ticket(fallback_analysis("Smoke and fire near the library"),
                           "Smoke and fire near the library", "Central Library", "fallback", db_path=db,
                           critical_alert=True).ticket
    assert ticket.critical_alert

    calls = []
    class Response:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return Response()
    monkeypatch.setattr("safety_alerts.urlopen", fake_urlopen)
    sent, recipients, configured = sms_safety_workers_critical_alert(ticket)
    assert (sent, recipients, configured) == (1, 1, True)
    assert len(calls) == 1 and calls[0][1] > 0
    fields = parse_qs(calls[0][0].data.decode())
    assert fields["To"] == ["+919999000001"] and fields["MessagingServiceSid"] == ["MGtest"]
    assert ticket.ticket_id in fields["Body"][0]
    assert calls[0][0].get_header("Authorization") == "Basic " + base64.b64encode(b"ACtest:secret-test-token").decode()


def test_sms_missing_provider_credentials_is_a_noop(db, monkeypatch):
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID", "TWILIO_FROM_PHONE"):
        monkeypatch.delenv(key, raising=False)
    ticket = create_ticket(fallback_analysis("Gas leak near the lab"), "Gas leak near the lab", None,
                           "fallback", db_path=db, critical_alert=True).ticket
    assert sms_safety_workers_critical_alert(ticket) == (0, 0, False)


def test_critical_report_submission_requests_one_sms_send(db, monkeypatch):
    import pages_report
    ticket = create_ticket(fallback_analysis("Fire near the dining hall"), "Fire near the dining hall", "Dining Hall",
                           "fallback", db_path=db, critical_alert=True).ticket
    created = SimpleNamespace(ticket=ticket, tracking_code="demo-code")
    send_sms = Mock(return_value=(1, 1, True))
    monkeypatch.setattr(pages_report, "rate_check", lambda *args, **kwargs: None)
    monkeypatch.setattr(pages_report, "finalize_submission", lambda *args, **kwargs: created)
    monkeypatch.setattr(pages_report, "email_staff_critical_alert", lambda *_: (0, 0, False))
    monkeypatch.setattr(pages_report, "sms_safety_workers_critical_alert", send_sms)
    monkeypatch.setattr(pages_report, "open_modal", lambda *args, **kwargs: None)
    monkeypatch.setattr(pages_report.st, "session_state", {})
    monkeypatch.setattr(pages_report.st, "rerun", lambda: None)
    pages_report._submit(None, {"id": 42}, [])
    send_sms.assert_called_once_with(ticket)


def test_sms_delivery_exception_does_not_escape_after_ticket_save(db, monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-test-token")
    monkeypatch.setenv("TWILIO_FROM_PHONE", "+15005550006")
    create_worker("Safety One", "safety-failure@t.edu", "safety-password-1",
                  "Campus Safety & Emergency Response", db_path=db, phone="+919999000001")
    ticket = create_ticket(fallback_analysis("Gas leak at the lab"), "Gas leak at the lab", "Lab",
                           "fallback", db_path=db, critical_alert=True).ticket
    monkeypatch.setattr("safety_alerts.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("private body")))
    assert sms_safety_workers_critical_alert(ticket) == (0, 1, True)
