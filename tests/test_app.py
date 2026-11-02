"""Headless UI tests using Streamlit's AppTest. No browser, no network, no API key.
Dialogs are driven by a session flag, so their buttons are testable like any other widget."""
import pathlib
import re
import sqlite3
from datetime import datetime, timedelta, timezone
import pytest
from streamlit.testing.v1 import AppTest
import ticket_service as ts
from ai_service import fallback_analysis
from auth_service import create_session, create_staff, register_student, user_from_session
from schemas import Status
from ticket_service import get_ticket, list_tickets

APP = str(pathlib.Path(__file__).resolve().parents[1] / "app.py")
TEXT = "No electricity in Hostel Block B since morning"
PW = "correct-horse-1"


@pytest.fixture
def at(db, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    a = AppTest.from_file(APP, default_timeout=40).run()
    assert not a.exception
    return a


def goto(at, page):
    at.radio(key="page").set_value(page).run()
    return at


def as_student(at, db, email="s@c.edu", name="Test Student"):
    u = register_student(name, email, PW, db_path=db)
    at.session_state["user"] = u.model_dump()
    return u


def as_staff(at, db, email="staff@c.edu", dept=None):
    u = create_staff("Test Staff", email, PW, db_path=db, department=dept)
    at.session_state["user"] = u.model_dump()
    return u


def ticket(db, text=TEXT, loc="Hostel Block B", reporter=None):
    return ts.create_ticket(fallback_analysis(text), text, loc, "fallback", reporter_id=reporter, db_path=db)


def submit(at, text=TEXT, loc="Hostel Block B (Boys)"):
    goto(at, "Report an issue")
    at.text_area(key="desc").input(text)
    at.selectbox(key="loc_sel").select(loc)
    at.button(key="analyze").click().run()
    return at


def page_text(at):
    return " ".join(m.value for m in at.markdown)


def fix(db, tid, staff):
    ts.update_status(tid, Status.IN_PROGRESS, actor=staff, db_path=db)
    ts.mark_fixed(tid, "Replaced the faulty fuse and tested.", actor=staff, db_path=db)


# ================================================================ access control
def test_report_page_requires_sign_in(at):
    goto(at, "Report an issue")
    assert at.button(key="gate_btn") and "analyze" not in [b.key for b in at.button]


def test_staff_page_requires_staff_account(at, db):
    as_student(at, db)
    goto(at, "Staff workspace")
    assert "Staff workspace" not in [getattr(o, "value", str(o)) for o in at.radio(key="page").options]


def test_staff_cannot_use_the_student_report_page(at, db):
    as_staff(at, db)
    goto(at, "Report an issue")
    assert "analyze" not in [b.key for b in at.button]


# ================================================================ landing portal: sign in / up / reset / demo
def test_home_shows_the_portal_when_signed_out_and_a_welcome_when_signed_in(at, db):
    assert [b.key for b in at.button if b.key in ("si_submit", "rg_submit", "rs_submit")] == ["si_submit", "rg_submit", "rs_submit"]
    assert "Clarity precedes resolution" not in page_text(at)
    as_student(at, db)
    at.run()
    assert "Welcome back" in page_text(at) and "si_submit" not in [b.key for b in at.button]


def test_private_demo_access_shows_credentials_and_signs_in_with_one_tap(at, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    at.run()
    assert at.button(key="demo_one_touch")
    assert any("student@demo.test" in str(c.value) and "DemoPass123" in str(c.value) for c in at.code)
    at.button(key="demo_one_touch").click().run()
    assert at.session_state["user"]["email"] == "student@demo.test"
    assert at.session_state["user"]["role"] == "student"


def test_student_can_open_emergency_page_and_tap_to_call_numbers(at, db):
    as_student(at, db)
    at.run()
    assert "Emergency" in at.radio(key="page").options
    goto(at, "Emergency")
    text = page_text(at)
    for number in ("112", "100", "101", "108", "102", "1090", "8744052891"):
        assert number in text
        assert f"tel:{number}" in text
    assert "tel:112" in text and "not identified as a 24-hour emergency line" in text


def test_worker_workspace_includes_campus_navigation_map(at, db):
    from ai_service import fallback_analysis
    from auth_service import create_worker
    from conftest import staff_for
    from ticket_service import assign_ticket, create_ticket
    worker = create_worker("Map Worker", "map-worker@t.edu", PW, "Electrical Maintenance", db_path=db)
    ticket = create_ticket(fallback_analysis("Power outage in the electrical lab"), "Power outage in the electrical lab",
                           "Central Library 2F", "fallback", db_path=db).ticket
    assign_ticket(ticket.ticket_id, worker.id, actor=staff_for(db), db_path=db)
    at.session_state["user"] = worker.model_dump()
    at.session_state["page"] = "Worker workspace"
    at.run()
    assert not at.exception
    assert "Campus map & directions" in [e.label for e in at.expander]
    assert any("Same AKGEC location map" in c.value for c in at.caption)


def test_staff_system_exposes_worker_account_edit_controls(at, db):
    from auth_service import create_worker
    worker = create_worker("Manage Worker", "manage-worker@t.edu", PW, "Electrical Maintenance", db_path=db)
    as_staff(at, db)
    goto(at, "Staff workspace")
    assert "Edit or remove a worker account" in [e.label for e in at.expander]
    assert f"edit_worker_name_{worker.id}" in [x.key for x in at.text_input]


def test_guests_can_open_emergency_contacts_without_signing_in(at):
    assert "Emergency" in at.radio(key="page").options
    goto(at, "Emergency")
    assert "Call India’s emergency number" in page_text(at)
    assert "tel:112" in page_text(at)


def test_student_registers_from_the_landing_page_and_lands_on_report(at, db):
    for k, v in (("rg_name", "Asha Rao"), ("rg_email", "asha@c.edu"), ("rg_pw", PW), ("rg_pw2", PW)):
        at.text_input(key=k).input(v)
    at.button(key="rg_submit").click().run()
    assert at.session_state["user"]["role"] == "student" and at.session_state["page"] == "Report an issue"


def test_mismatched_passwords_are_refused(at):
    for k, v in (("rg_name", "Asha Rao"), ("rg_email", "asha@c.edu"), ("rg_pw", PW), ("rg_pw2", "different-pw-1")):
        at.text_input(key=k).input(v)
    at.button(key="rg_submit").click().run()
    assert "user" not in at.session_state and any("do not match" in e.value for e in at.error)


def test_wrong_password_and_unknown_email_give_the_same_error(at, db):
    register_student("Asha", "asha@c.edu", PW, db_path=db)
    msgs = []
    for email, pw in (("asha@c.edu", "wrong-password"), ("nobody@c.edu", PW)):
        at.text_input(key="si_email").input(email); at.text_input(key="si_pw").input(pw)
        at.button(key="si_submit").click().run()
        msgs.append([e.value for e in at.error])
    assert msgs[0] == msgs[1] and "Incorrect email or password" in msgs[0][0] and "user" not in at.session_state


def test_a_student_cannot_sign_in_through_the_staff_option(at, db):
    register_student("Asha", "asha@c.edu", PW, db_path=db)
    at.radio(key="si_role").set_value("Staff").run()
    at.text_input(key="si_email").input("asha@c.edu"); at.text_input(key="si_pw").input(PW)
    at.button(key="si_submit").click().run()
    assert "user" not in at.session_state and any("Incorrect email or password" in e.value for e in at.error)


def test_staff_sign_in_opens_the_workspace_and_sign_out_revokes_the_session(at, db):
    create_staff("Meera K", "meera@c.edu", PW, db_path=db)
    at.radio(key="si_role").set_value("Staff").run()
    at.text_input(key="si_email").input("meera@c.edu"); at.text_input(key="si_pw").input(PW)
    at.button(key="si_submit").click().run()
    assert at.session_state["user"]["role"] == "staff" and at.session_state["page"] == "Staff workspace"
    tok = at.query_params["s"]; tok = tok[0] if isinstance(tok, list) else tok
    assert user_from_session(tok, db_path=db) is not None
    goto(at, "Account")
    at.button(key="logout").click().run()
    assert "user" not in at.session_state and user_from_session(tok, db_path=db) is None and "s" not in at.query_params


def test_demo_accounts_appear_only_in_demo_mode_and_sign_in_with_one_click(db, monkeypatch):
    off = AppTest.from_file(APP, default_timeout=40).run()
    assert "demo_one_touch" not in [b.key for b in off.button]
    monkeypatch.setenv("DEMO_MODE", "1")
    on = AppTest.from_file(APP, default_timeout=40).run()
    assert "demo_one_touch" in [b.key for b in on.button]
    assert any("student@demo.test" in str(c.value) for c in on.code)
    on.button(key="demo_one_touch").click().run()
    assert on.session_state["user"]["name"] == "Alex Rivera" and on.session_state["page"] == "Report an issue"
    out = AppTest.from_file(APP, default_timeout=40).run()
    out.radio(key="demo_role").set_value("Staff").run()
    out.button(key="demo_one_touch").click().run()
    assert out.session_state["user"]["department"] == "Plumbing" and out.session_state["page"] == "Staff workspace"
    worker = AppTest.from_file(APP, default_timeout=40).run()
    worker.radio(key="demo_role").set_value("Worker").run()
    worker.button(key="demo_one_touch").click().run()
    assert worker.session_state["user"]["role"] == "worker" and worker.session_state["page"] == "Worker workspace"


def test_forgot_password_flow(at, db):
    from auth_service import authenticate, issue_reset_code
    register_student("Asha", "asha@c.edu", PW, db_path=db)
    code = issue_reset_code("asha@c.edu", actor=create_staff("Meera", "meera@c.edu", PW, db_path=db), db_path=db)
    for k, v in (("rs_email", "asha@c.edu"), ("rs_code", code), ("rs_pw", "brand-new-pass-2")):
        at.text_input(key=k).input(v)
    at.button(key="rs_submit").click().run()
    assert any("Password updated" in s.value for s in at.success)
    assert authenticate("asha@c.edu", "brand-new-pass-2", role="student", db_path=db).role == "student"


def test_session_survives_a_refresh_and_a_forged_token_gets_nothing(db):
    u = register_student("Asha", "asha@c.edu", PW, db_path=db)
    ok = AppTest.from_file(APP, default_timeout=40); ok.query_params["s"] = create_session(u.id, db_path=db); ok.run()
    bad = AppTest.from_file(APP, default_timeout=40); bad.query_params["s"] = "forged-token"; bad.run()
    assert ok.session_state["user"]["email"] == "asha@c.edu" and "user" not in bad.session_state


# ================================================================ reporting window
def test_short_description_is_blocked(at, db):
    as_student(at, db)
    submit(at, "help")
    assert at.error and "at least a sentence" in at.error[0].value and list_tickets(db_path=db) == []


def test_report_flow_shows_a_real_pipeline_then_a_celebration_and_links_the_student(at, db):
    u = as_student(at, db)
    submit(at)
    text = page_text(at)
    assert "[1/4] Input validated" in text and "[2/4] AI analysis" in text and "[4/4] Duplicate check" in text
    assert list_tickets(db_path=db) == [] and {f.key for f in at.get("file_uploader")} == {"voice_upload", "photos"}
    at.button(key="create").click().run()
    c = at.session_state["created"]
    assert re.fullmatch(r"RAI-\d{4}-0001", c.ticket.ticket_id) and get_ticket(c.ticket.ticket_id, db).reporter_id == u.id
    assert get_ticket(c.ticket.ticket_id, db).location == "Hostel Block B (Boys)"
    assert at.session_state["modal"]["kind"] == "submitted" and 'class="cf"' in page_text(at)  # pop-up and confetti on submission
    at.run()
    assert 'class="cf"' not in page_text(at)  # confetti plays once, not on every refresh
    at.button(key="sub_track").click().run()
    assert at.session_state["page"] == "Track a ticket" and "modal" not in at.session_state  # the pop-up's button really navigates


def test_duplicate_is_offered_and_linking_keeps_both(at, db):
    as_student(at, db)
    submit(at); at.button(key="create").click().run()
    at.button(key="sub_close").click().run(); at.button(key="again").click().run()
    submit(at, "Power cut, no electricity in Hostel Block B")
    assert at.button(key="link0") and at.button(key="new_anyway")
    at.button(key="link0").click().run()
    rows = list_tickets(db_path=db)
    assert len(rows) == 2 and any(r.duplicate_of for r in rows)


def test_students_get_a_friendly_analysis_limit(at, db, monkeypatch):
    monkeypatch.setenv("RATE_ANALYSES_PER_HOUR", "1")
    as_student(at, db)
    submit(at)
    at.button(key="analyze").click().run()
    assert any("reached the limit" in e.value for e in at.error)


# ================================================================ tracking window and the sign-off handshake
def test_a_student_sees_only_their_own_reports(at, db):
    stu = as_student(at, db)
    mine = ticket(db, reporter=stu.id).ticket.ticket_id
    other = register_student("Other", "o@c.edu", PW, db_path=db)
    theirs = ticket(db, "Private complaint about the warden office", None, other.id).ticket.ticket_id
    goto(at, "Track a ticket")
    assert mine in page_text(at) and theirs not in page_text(at)


def test_pending_fix_shows_an_action_banner_and_the_student_can_confirm_with_confetti(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    fix(db, tid, create_staff("Mario", "m@c.edu", PW, db_path=db))
    goto(at, "Track a ticket")
    assert "Action needed" in page_text(at) and at.radio(key="tfilter").value == "wait"
    at.button(key=f"signoff_{tid}").click().run()
    assert at.session_state["modal"]["kind"] == "signoff" and at.button(key="so_go")
    at.radio(key="so_rating").set_value(5)
    at.text_area(key="so_comment").input("Lights are back, thank you")
    at.button(key="so_go").click().run()
    t = get_ticket(tid, db)
    assert t.status == Status.RESOLVED and t.resolved_by == "student" and t.rating == 5 and "modal" not in at.session_state
    assert 'class="cf"' in page_text(at)


def test_student_reopens_with_a_reason_and_staff_see_it(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    staff = create_staff("Mario", "m@c.edu", PW, db_path=db)
    fix(db, tid, staff)
    goto(at, "Track a ticket")
    at.button(key=f"reopen_{tid}").click().run()
    at.text_area(key="ro_reason").input("x")
    at.button(key="ro_go").click().run()
    assert any("at least 10" in e.value for e in at.error) and get_ticket(tid, db).status == Status.PENDING  # a reason is required
    at.text_area(key="ro_reason").input("The corridor lights are still dead")
    at.button(key="ro_go").click().run()
    assert get_ticket(tid, db).status == Status.REOPENED and get_ticket(tid, db).reopen_count == 1
    assert any("still dead" in i["text"] for i in ts.get_timeline(tid, actor=staff, db_path=db))


def test_student_can_resolve_their_own_ticket(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    goto(at, "Track a ticket")
    at.button(key=f"own_{tid}").click().run()
    at.text_input(key="own_note").input("The power came back")
    at.button(key="own_go").click().run()
    assert get_ticket(tid, db).status == Status.RESOLVED and get_ticket(tid, db).resolved_by == "student"


def test_student_comments_reach_the_team(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    goto(at, "Track a ticket")
    at.text_input(key=f"cm_{tid}").input("It is getting worse")
    at.button(key=f"addc_{tid}").click().run()
    staff = create_staff("Mario", "m@c.edu", PW, db_path=db)
    assert any(i["kind"] == "student" and "worse" in i["text"] for i in ts.get_timeline(tid, actor=staff, db_path=db))


def test_guest_lookup_works_with_the_code_and_locks_after_repeated_misses(at, db):
    c = ticket(db)
    tid, code = c.ticket.ticket_id, c.tracking_code
    g = AppTest.from_file(APP, default_timeout=40).run()
    goto(g, "Track a ticket")
    g.text_input(key="tid").input(tid)
    g.text_input(key="tcode").input(code)
    g.button(key="check").click().run()
    assert tid in page_text(g)
    for _ in range(5):
        g.text_input(key="tcode").input("0000-0000"); g.button(key="check").click().run()
    g.text_input(key="tcode").input(code); g.button(key="check").click().run()
    assert any("Too many" in e.value for e in g.error)


def test_signed_out_visitors_are_asked_to_sign_in_on_the_track_page(at):
    goto(at, "Track a ticket")
    assert at.button(key="track_signin") and "Sign in as a student" in page_text(at)


# ================================================================ photos
def test_staff_and_the_owner_see_photos_but_other_students_do_not(at, db):
    import io
    from PIL import Image
    from attachments import save_image
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    b = io.BytesIO(); Image.new("RGB", (80, 60), (10, 120, 200)).save(b, "JPEG")
    save_image(tid, b.getvalue(), "wiring.jpg", kind="report", uploader_id=stu.id)
    goto(at, "Track a ticket")
    assert len(at.get("image")) == 1
    other = AppTest.from_file(APP, default_timeout=40).run(); as_student(other, db, "o@c.edu", "Other Student"); goto(other, "Track a ticket")
    assert len(other.get("image")) == 0
    staff = AppTest.from_file(APP, default_timeout=40).run(); as_staff(staff, db); goto(staff, "Staff workspace")
    assert len(staff.get("image")) == 1


# ================================================================ staff workspace
def test_queue_counts_first_ticket_selected_and_empty_queue_message(at, db):
    ticket(db); ticket(db, "Wi-Fi down in the library", "Library")
    as_staff(at, db)
    goto(at, "Staff workspace")
    assert at.selectbox(key="queue").value == "active" and at.session_state["sel"] is not None
    assert at.selectbox(key="queue").options and at.selectbox(key="queue").value == "active"
    at.selectbox(key="queue").set_value("mine").run()
    assert "Nothing in this queue" in page_text(at)


def test_department_queue_is_the_default_for_staff_with_a_department(at, db):
    ticket(db, "Tap is leaking in the Lab 3 washroom", "Lab 3"); ticket(db)
    as_staff(at, db, dept="Plumbing")
    goto(at, "Staff workspace")
    assert at.selectbox(key="queue").value == "department"


def test_assigning_moves_a_ticket_to_my_queue(at, db):
    tid = ticket(db).ticket.ticket_id
    staff = as_staff(at, db)
    goto(at, "Staff workspace")
    at.button(key=f"doasg_{tid}").click().run()
    assert get_ticket(tid, db).assignee_id == staff.id
    at.selectbox(key="queue").set_value("mine").run()
    assert "trow" in page_text(at) and tid in page_text(at)


def test_staff_mark_a_ticket_fixed_through_the_dialog_and_it_waits_for_the_student(at, db):
    tid = ticket(db).ticket.ticket_id
    as_staff(at, db)
    goto(at, "Staff workspace")
    at.button(key=f"start_{tid}").click().run()
    assert get_ticket(tid, db).status == Status.IN_PROGRESS
    at.button(key=f"fix_{tid}").click().run()
    assert at.session_state["modal"]["kind"] == "fix"
    at.text_area(key="fx_note").input("short")
    at.button(key="fx_go").click().run()
    assert any("at least 10" in e.value for e in at.error) and get_ticket(tid, db).status == Status.IN_PROGRESS
    at.text_area(key="fx_note").input("Replaced the faulty fuse and tested the circuit")
    at.button(key="fx_go").click().run()
    t = get_ticket(tid, db)
    assert t.status == Status.PENDING and t.fixed_at is not None and "modal" not in at.session_state
    at.selectbox(key="queue").set_value("awaiting").run()
    assert tid in page_text(at) and "Waiting for the student" in page_text(at)


def test_staff_cannot_close_an_unanswered_fix_until_the_waiting_period_ends(at, db):
    tid = ticket(db).ticket.ticket_id
    staff = as_staff(at, db)
    fix(db, tid, staff)
    goto(at, "Staff workspace"); at.selectbox(key="queue").set_value("awaiting").run()
    assert f"close_{tid}" not in [b.key for b in at.button]
    with sqlite3.connect(db) as c:
        c.execute("UPDATE tickets SET fixed_at = ?", ((datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds"),))
    at.run()
    at.button(key=f"close_{tid}").click().run()
    at.button(key="ct_go").click().run()
    assert get_ticket(tid, db).status == Status.RESOLVED and get_ticket(tid, db).resolved_by == "staff_timeout"


def test_reopened_tickets_get_their_own_queue(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    staff = create_staff("Mario", "m@c.edu", PW, db_path=db)
    fix(db, tid, staff)
    ts.student_signoff(tid, actor=stu, confirm=False, comment="The lights are still dead", db_path=db)
    at.session_state["user"] = staff.model_dump()
    goto(at, "Staff workspace")
    assert any("Reopened" in option and "1" in option for option in at.selectbox(key="queue").options)
    at.selectbox(key="queue").set_value("reopened").run()
    assert tid in page_text(at) and "not fixed" in page_text(at)


def test_internal_notes_stay_internal_and_public_notes_reach_the_student(at, db):
    stu = as_student(at, db)
    tid = ticket(db, reporter=stu.id).ticket.ticket_id
    as_staff(at, db)
    goto(at, "Staff workspace")
    at.text_area(key=f"nt{tid}").input("Reporter exaggerates, check first")
    at.button(key=f"addnote{tid}").click().run()
    at.text_area(key=f"nt{tid}").input("An electrician will visit this afternoon.")
    at.radio(key=f"nv{tid}").set_value("Visible to the student")
    at.button(key=f"addnote{tid}").click().run()
    assert "exaggerates" in page_text(at) and "staff only" in page_text(at)
    at.session_state["user"] = stu.model_dump()
    at.session_state["page"] = "Home"  # emulate the app's post-sign-out role switch
    at.run()
    goto(at, "Track a ticket")
    text = page_text(at)
    assert "electrician will visit" in text and "exaggerates" not in text


def test_bulk_actions_need_confirmation_then_apply(at, db):
    a, b = ticket(db).ticket.ticket_id, ticket(db, "Wi-Fi down in the library", "Library").ticket.ticket_id
    staff = as_staff(at, db)
    goto(at, "Staff workspace")
    at.multiselect(key="bulk_ids").select(a).select(b).run()
    assert at.button(key="bulk_me").disabled
    at.checkbox(key="bulk_ok").check().run()
    at.button(key="bulk_me").click().run()
    assert get_ticket(a, db).assignee_id == staff.id and get_ticket(b, db).assignee_id == staff.id


def test_possible_duplicates_can_be_linked_by_staff(at, db):
    first = ticket(db).ticket.ticket_id
    second = ticket(db, "Power cut, no electricity in Hostel Block B", "Hostel Block B").ticket.ticket_id
    as_staff(at, db)
    goto(at, "Staff workspace")
    at.session_state["sel"] = second; at.run()
    at.button(key=f"lk_{second}_{first}").click().run()
    assert get_ticket(second, db).duplicate_of == first


def test_overview_system_export_and_reset_code_for_staff(at, db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret-value")
    register_student("Asha", "asha@c.edu", PW, db_path=db)
    ticket(db)
    as_staff(at, db)
    goto(at, "Staff workspace")
    text = page_text(at)
    assert "Schema v16" in text and "sk-super-secret-value" not in text and "Median time to fix" in text
    assert len(at.get("download_button")) == 1
    at.text_input(key="rc_email").input("asha@c.edu").run(); at.button(key="rc_issue").click().run()
    assert at.code and re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}", at.code[0].value)


def test_staff_ticket_details_show_the_saved_triage_record(at, db):
    tid = ticket(db).ticket.ticket_id
    as_staff(at, db)
    goto(at, "Staff workspace")
    t = page_text(at)
    assert tid in t and "Original complaint" in t and "No electricity" in t
