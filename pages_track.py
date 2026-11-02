from datetime import datetime, timezone
import streamlit as st
import sla
from dialogs import open_modal
from schemas import LIVE_STATUSES, Status
from shared import PAGES, current_user, go, show_photos
from ticket_service import TicketError, WITHDRAWAL_REASONS, WITHDRAWAL_WINDOW_MINUTES, add_student_comment, get_public_status, list_tickets, student_timeline, withdraw_ticket
from ui import cat_tag, h, kpi, md, page_head, status, stepper, tag

FILTERS = {"all": "All", "open": "Open", "progress": "In progress", "wait": "Awaiting your sign-off", "reopened": "Reopened", "done": "Resolved", "withdrawn": "Withdrawn / removed"}


def _match(t, k):
    return {"all": True, "open": t.status == Status.OPEN, "progress": t.status == Status.IN_PROGRESS, "wait": t.status == Status.PENDING,
            "reopened": t.status == Status.REOPENED, "done": t.status == Status.RESOLVED, "withdrawn": t.status == Status.WITHDRAWN}[k]


def _add_comment(tid):
    body = st.session_state.get(f"cm_{tid}", "")
    try:
        add_student_comment(tid, body, actor=current_user())
        st.session_state[f"cm_{tid}"] = ""
        st.session_state["flash"] = ("ok", "Your comment was sent to the team.")
    except TicketError as e:
        st.session_state["flash"] = ("err", str(e))


def _timeline_html(items):
    css = {"event": "event", "staff": "public", "student": "student"}
    return '<ul class="tl2">' + "".join(
        f'<li class="{css[i["kind"]]}"><b>{h(i["who"])}</b> ' + (f'<span class="nb">{h(i["text"])}</span>' if i["kind"] != "event" else h(i["text"])) + f'<small>{h(i["at"][:16].replace("T", " "))} UTC</small></li>'
        for i in reversed(items)) + "</ul>"


def _card(t, me):
    wait, tid = t.status == Status.PENDING, t.ticket_id
    with st.container(key=f"tk_{tid}"):
        md(f'<span class="pcm-{h(t.priority.value)}"></span>' + ('<span class="pcm-wait"></span>' if wait else "")
           + f'<div class="tk-h">{status(t.status.value)} {cat_tag(t.category.value)}' + (tag("Linked to " + t.duplicate_of, "b") if t.duplicate_of else "") + f'<span class="id">{h(tid)}</span></div>'
           f'<div class="tk-t">{h(t.summary)}</div><div class="tk-m"><span>Filed {t.created_at:%d %b %Y}</span><span>Resolve by {sla.due_at(t):%d %b %Y, %H:%M} UTC</span><span>{h(t.location or "No location given")}</span><span>Handled by {h(t.department)}</span>'
           f'<span>Updated {t.updated_at:%d %b %H:%M}</span></div>' + stepper(t.status.value))
        if wait:
            md(f'<div class="callout wait"><b>The team says it is fixed. Can you confirm?</b><br>{h(t.resolution_note or "")}</div>')
        elif t.status == Status.REOPENED:
            md(f'<div class="callout bad"><b>You reopened this ticket</b> ({t.reopen_count} time{"s" if t.reopen_count != 1 else ""}). The team has been told and will look again.</div>')
        elif t.status == Status.RESOLVED:
            who = {"student": "You closed this ticket", "staff_timeout": "The team closed this ticket after no reply"}.get(t.resolved_by or "", "Closed")
            md(f'<div class="callout ok"><b>{who}.</b>' + (f' Your rating: {"★" * t.rating}{"☆" * (5 - t.rating)}' if t.rating else "") + (f"<br>Fix: {h(t.resolution_note)}" if t.resolution_note else "") + "</div>")
        elif t.staff_removed:
            md(f'<div class="callout bad"><b>Removed from active work by the campus team.</b><br>Reason: {h(t.staff_removal_reason or "No reason was provided.")}<br>Your report history is retained. If the issue still needs attention, submit a new report or contact the campus team.</div>')
        elif t.status == Status.WITHDRAWN:
            md(f'<div class="callout wait"><b>You withdrew this report.</b> It remains in the record for staff review.<br>Reason: {h(t.withdrawal_reason or "Not recorded")}'
               + ('<br><b>This withdrawal was flagged for staff review due to a repeated pattern.</b>' if t.withdrawal_review else '') + '</div>')
        with st.container(key=f"phs_{tid}"):
            show_photos(tid, me)
        b = st.columns([1.4, 1, 1, 1.6])
        if wait:
            b[0].button("Yes, it is fixed", type="primary", key=f"signoff_{tid}", on_click=open_modal, args=("signoff",), kwargs={"tid": tid})
            b[1].button("Not fixed", key=f"reopen_{tid}", on_click=open_modal, args=("reopen",), kwargs={"tid": tid})
        # Pending tickets already have a dedicated student sign-off action.
        if t.status in LIVE_STATUSES:
            b[2].button("Mark resolved", key=f"own_{tid}", on_click=open_modal, args=("resolve_own",), kwargs={"tid": tid})
        b[3].button("How was this handled?", key=f"pipe_{tid}", on_click=open_modal, args=("pipeline",), kwargs={"tid": tid})
        with st.expander("Timeline and comments"):
            md(_timeline_html(student_timeline(tid, actor=me)))
            if t.status not in (Status.RESOLVED, Status.WITHDRAWN):
                c1, c2 = st.columns([4, 1])
                c1.text_input("Add a comment", key=f"cm_{tid}", label_visibility="collapsed", placeholder="Add a comment for the team", max_chars=1000)
                c2.button("Send", key=f"addc_{tid}", on_click=_add_comment, args=(tid,))
        if t.status == Status.OPEN and t.assignee_id is None:
            with st.expander("Withdraw this report"):
                age = (datetime.now(timezone.utc) - (t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc))).total_seconds()
                if age <= WITHDRAWAL_WINDOW_MINUTES * 60:
                    st.caption(f"Available for {WITHDRAWAL_WINDOW_MINUTES} minutes after submission, while the report is open and unassigned. The report and its history will be retained for staff.")
                    reason_options = ["Choose a reason…", *WITHDRAWAL_REASONS]
                    reason = st.selectbox("Why are you withdrawing it?", reason_options, key=f"withdraw_reason_{tid}")
                    confirmed = st.checkbox("I confirm I want to withdraw this report", key=f"student_withdraw_confirm_{tid}")
                    if st.button("Withdraw my report", key=f"student_withdraw_{tid}", disabled=not confirmed or reason == reason_options[0]):
                        try:
                            result = withdraw_ticket(tid, reason, actor=me)
                            st.session_state["flash"] = ("ok", "Report withdrawn. Its history is retained for staff.")
                            if result.withdrawal_review:
                                st.session_state["flash"] = ("ok", "Report withdrawn and flagged for staff review. Its history is retained.")
                            st.rerun()
                        except TicketError as e:
                            st.error(str(e))
                else:
                    st.caption(f"The {WITHDRAWAL_WINDOW_MINUTES}-minute withdrawal window has passed. The report remains in your ticket history.")


def _guest_lookup(expanded):
    with st.expander("Look up one ticket with its ID and tracking code", expanded=expanded):
        left, right = st.columns(2, gap="large")
        with left:
            tid = st.text_input("Ticket ID", key="tid", placeholder="RAI-2026-0001")
            code = st.text_input("Tracking code", key="tcode", placeholder="ABCD-1234")
            clicked = st.button("Check status →", type="primary", key="check")
        with right:
            with st.container(key="panel_track"):
                if not clicked:
                    md('<div class="ph">Your ticket status will appear here.</div>')
                    return
                s, lock = None, None
                try:
                    s = get_public_status(tid, code)
                except TicketError as e:
                    lock = str(e)
                if lock:
                    st.error(lock)
                elif not s:
                    st.error("We couldn’t find a ticket with that ID and tracking code.")
                else:
                    md(f'<div class="idbig">{h(s.ticket_id)}</div><p>{status(s.status.value)}</p>' + stepper(s.status.value) + f'<dl class="out"><dt>Summary</dt><dd>{h(s.summary)}</dd>'
                       f'<dt>Category</dt><dd>{h(s.category.value)}</dd><dt>Reported</dt><dd>{s.created_at:%d %b %Y %H:%M}</dd><dt>Updated</dt><dd>{s.updated_at:%d %b %Y %H:%M}</dd>'
                       + (f'<dt>Resolve by</dt><dd>{s.deadline_at:%d %b %Y %H:%M} UTC</dd>' if s.deadline_at else "")
                       + (f'<dt>Notice</dt><dd>{h("Removed from active work by the campus team. Reason: " + (s.staff_removal_reason or "No reason was provided."))}</dd>' if s.staff_removed else "")
                       + (f'<dt>Latest fix note</dt><dd>{h(s.resolution_note)}</dd>' if s.resolution_note else "")
                       + "".join(f'<dt>Update</dt><dd style="font-weight:400">{h(u["text"])}</dd>' for u in s.updates) + "</dl>")


def render():
    me = current_user()
    if me and me.role == "student":
        md(f'<section class="student-portal-banner"><div class="student-mark">S</div><div><div class="eyebrow">STUDENT PORTAL · MY REQUESTS</div><div class="student-banner-title">Your campus reports</div><p>Track progress, reply to staff, and confirm when a fix works for you.</p></div><div class="student-banner-step">02 <span>TRACK</span></div></section>')
    page_head("Track a ticket", "Where are my reports?", "Follow each report from submission to resolution. When the team says it is fixed, you decide whether it really is.")
    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] == "ok" else st.error)(flash[1])
    if not me or me.role != "student":
        md('<div class="callout wait"><b>Sign in as a student</b> to see all of your reports, confirm fixes, and add comments.</div>')
        st.button("Go to sign in →", type="primary", key="track_signin", on_click=go, args=(PAGES[5],))
        _guest_lookup(True)
        return
    mine = sorted(list_tickets(reporter_id=me.id), key=lambda t: t.created_at, reverse=True)
    waiting = [t for t in mine if t.status == Status.PENDING]
    if waiting:
        md(f'<div class="banner"><b>Action needed:</b> {len(waiting)} fix{"es are" if len(waiting) != 1 else " is"} waiting for your sign-off. Please check and confirm below.</div>')
    md('<div class="kpis three" style="grid-template-columns:repeat(4,1fr)">' + kpi("Reports filed", len(mine), "#2F6FED") + kpi("Being worked on", sum(t.status in LIVE_STATUSES for t in mine), "#D98E04")
       + kpi("Waiting for you", len(waiting), "#7A5AF8") + kpi("Resolved", sum(t.status == Status.RESOLVED for t in mine), "#2E9E5B") + "</div>")
    if not mine:
        md('<div class="ph">You have not filed a report yet.</div>')
        st.button("Report an issue →", type="primary", key="track_report", on_click=go, args=(PAGES[1],))
    else:
        counts = {k: sum(_match(t, k) for t in mine) for k in FILTERS}
        st.session_state.setdefault("tfilter", "wait" if waiting else "all")
        st.radio("Filter", list(FILTERS), format_func=lambda k: f"{FILTERS[k]} ({counts[k]})", horizontal=True, key="tfilter", label_visibility="collapsed")
        shown = [t for t in mine if _match(t, st.session_state["tfilter"])]
        limit = st.session_state.setdefault("tlimit", 6)
        for t in shown[:limit]:
            _card(t, me)
        if not shown:
            md('<div class="ph">Nothing here.</div>')
        if len(shown) > limit:
            st.button(f"Show more ({len(shown) - limit} left)", key="more_t", on_click=lambda: st.session_state.update(tlimit=limit + 6))
    _guest_lookup(False)
