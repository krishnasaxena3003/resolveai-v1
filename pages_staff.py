from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import pandas as pd
import plotly.express as px
import streamlit as st
import metrics
import sla
from analytics import counts, to_csv
from auth_service import (AuthError, create_worker, delete_worker_account, issue_reset_code, list_worker_accounts,
                          list_worker_contacts, update_worker_account)
from config import get_settings
from dialogs import open_modal
from duplicate_service import find_candidates
from healthcheck import check as health_check
from schemas import DEPARTMENTS, LIVE_STATUSES, SAFETY_DEPARTMENT, Category, Priority, Status, User
from shared import require, show_photos, style_fig
from ticket_service import (TicketError, add_comment, assign_ticket, bulk_assign, bulk_status, correct_fields, get_ticket, get_timeline, list_staff,
                            delete_ticket, set_duplicate_link, staff_critical_tickets, staff_list_tickets, update_deadline, update_status, update_ticket_details)
from ui import CAT_HEX, PRI_HEX, STATUS_HEX, cat_tag, h, kpi, md, page_head, pri, sla_chip, status, tag
from voice_ui import render_voice_dictation

PR = {"High": 3, "Medium": 2, "Low": 1}
QL = {"critical": "Critical safety", "department": "My department", "active": "Active", "mine": "My queue", "unassigned": "Unassigned", "review": "Needs review", "overdue": "Overdue",
      "awaiting": "Waiting for student", "reopened": "Reopened", "resolved": "Resolved", "withdrawal_review": "Withdrawal review", "withdrawn": "Withdrawn / removed", "all": "All"}


def _select_critical_ticket(ticket_id):
    st.session_state["sel"] = ticket_id
    st.session_state["queue"] = "critical"
    st.rerun()


@st.fragment(run_every="30s")
def _live_safety_alerts(actor):
    alerts = staff_critical_tickets(actor=actor)
    if alerts:
        st.error(f"🚨 {len(alerts)} active potential life-safety alert(s) · Campus Safety & Emergency Response")
        for ticket in alerts[:5]:
            a, b = st.columns([4, 1.3], vertical_alignment="center")
            a.markdown(f"**{h(ticket.ticket_id)}** · {h(ticket.summary)}  \n{h(ticket.location or 'Location not provided')} · target {ticket.deadline_at:%H:%M UTC}" if ticket.deadline_at else f"**{h(ticket.ticket_id)}** · {h(ticket.summary)}")
            b.button("Review now", key=f"safety_open_{ticket.ticket_id}", on_click=_select_critical_ticket, args=(ticket.ticket_id,), type="primary")
        st.caption("This alert panel refreshes every 30 seconds while this staff workspace is open. Immediate danger still requires direct emergency contact.")


def _timeline(items):
    cls = {"event": "event", "internal": "internal", "public": "public", "student": "student"}
    note = {"public": " · student can see this", "internal": " · staff only", "student": " · from the student"}
    return '<ul class="tl2">' + "".join(f'<li class="{cls[i["kind"]]}"><b>{h(i["who"])}</b> ' + (f'<span class="nb">{h(i["text"])}</span>' if i["kind"] != "event" else h(i["text"]))
                                        + f'<small>{h(i["at"][:16].replace("T", " "))} UTC{note.get(i["kind"], "")}</small></li>' for i in reversed(items)) + "</ul>"


def render():
    settings = get_settings()
    staff = require("staff", "Staff workspace", "Staff accounts are created by an administrator. Sign in with your staff account to manage the ticket queue.")
    actor = User(**staff)
    dept = staff.get("department")
    now = datetime.now(timezone.utc)
    tickets = staff_list_tickets(actor=actor)
    _live_safety_alerts(actor)
    worker_accounts = list_worker_accounts(actor=actor)
    staff_users = list_staff(actor=actor)
    names = {u.id: u.name for u in staff_users}
    names.update({w["id"]: f'{w["name"]} · Removed' for w in worker_accounts if not w["is_active"]})
    dept_of = {u.id: u.department for u in staff_users}
    role_of = {u.id: u.role for u in staff_users}

    def in_queue(t, k):
        live = t.status in LIVE_STATUSES
        return {"critical": live and t.critical_alert, "department": live and bool(dept) and t.department == dept, "active": live, "mine": live and t.assignee_id == actor.id, "unassigned": live and t.assignee_id is None,
                "review": live and t.review_required, "overdue": sla.is_overdue(t, now), "awaiting": t.status == Status.PENDING, "reopened": t.status == Status.REOPENED,
                "resolved": t.status == Status.RESOLVED, "withdrawal_review": t.status == Status.WITHDRAWN and t.withdrawal_review,
                "withdrawn": t.status == Status.WITHDRAWN, "all": True}[k]

    queues = [k for k in QL if k != "department" or dept]
    qn = {k: sum(in_queue(t, k) for t in tickets) for k in queues}
    md('<section class="staff-hero"><div><div class="eyebrow">RESOLVEAI · OPERATIONS</div>'
       '<div class="staff-title">Staff workspace</div>'
       f'<p>Welcome back, <b>{h(staff["name"])}</b> · {h(dept or "All departments")}. Keep reports moving and give students clear updates.</p>'
       '</div><div class="staff-live"><i></i>Queue overview</div></section>')
    live_count = sum(t.status in LIVE_STATUSES for t in tickets)
    md('<div class="staff-metrics">'
       + kpi("Active tickets", live_count, "#2F6FED")
       + kpi("Needs attention", qn.get("review", 0) + qn.get("overdue", 0), "#E4572E")
       + kpi("Unassigned", qn.get("unassigned", 0), "#D98E04")
       + kpi("Resolved", qn.get("resolved", 0), "#2E9E5B")
       + '</div>')
    t_q, t_ov, t_sys = st.tabs(["Queue", "Overview", "System"])

    def select(tid):
        st.session_state["sel"] = tid

    def save_note(tid):
        g = st.session_state.get
        try:
            add_comment(tid, g(f"nt{tid}", ""), "public" if g(f"nv{tid}") == "Visible to the student" else "internal", actor=actor)
            st.session_state[f"nt{tid}"] = ""
            st.session_state["flash"] = ("ok", "Note saved and verified.")
        except TicketError as e:
            st.session_state["flash"] = ("err", str(e))

    # ------------------------------------------------------------ QUEUE
    with t_q:
        flash = st.session_state.pop("flash", None)
        if flash:
            (st.success if flash[0] == "ok" else st.error)(flash[1])
        with st.expander("Demo data", expanded=not tickets):
            st.caption("Adds up to ten fictional, clearly labelled tickets for demos. Existing sample records are skipped; Campus Intelligence excludes samples by default.")
            if st.button("Generate 10 labelled sample tickets", key="seed"):
                from seed import seed_sample_tickets
                made = seed_sample_tickets()
                message = f"Generated {made} distinct sample ticket(s). Each is labelled Sample." if made else "All ten sample tickets are already in the database."
                st.session_state["flash"] = ("ok", message)
                st.rerun()
        if not tickets:
            st.info("No tickets yet. Students file reports from the Report an issue page.")
        else:
            st.session_state.setdefault("queue", "department" if dept else "active")
            if st.session_state["queue"] not in queues:
                st.session_state["queue"] = "active"
            st.selectbox("Queue", queues, format_func=lambda k: f"{QL[k]}  ·  {qn[k]}", key="queue")
            lst, det = st.columns([1.05, 1.45], gap="medium")
            with lst:
                f1, f2 = st.columns([1.3, 1])
                q = f1.text_input("Search", key="fq", placeholder="Search tickets", label_visibility="collapsed")
                fp = f2.selectbox("Priority", ["All priorities"] + [p.value for p in Priority], key="fp", label_visibility="collapsed")
                rows = [t for t in tickets if in_queue(t, st.session_state["queue"]) and (fp == "All priorities" or t.priority.value == fp)
                        and (not q or q.lower() in f"{t.ticket_id} {t.summary} {t.location or ''} {t.description}".lower())]
                rows.sort(key=lambda t: (not t.critical_alert, -PR[t.priority.value], sla.due_at(t)))
                sel = st.session_state.get("sel")
                if sel not in {t.ticket_id for t in tickets}:
                    sel = rows[0].ticket_id if rows else None
                    st.session_state["sel"] = sel
                limit = st.session_state.setdefault("limit", 15)
                md(f'<div class="eyebrow" style="margin:2px 0 8px">{len(rows)} ticket{"s" if len(rows) != 1 else ""} · safety alerts first, then priority and due time</div>')
                for t in rows[:limit]:
                    ca, cb = st.columns([4, 1.15])
                    stt = sla.state(t, now)[0]
                    ca.markdown(f'<div class="trow{" sel" if t.ticket_id == sel else ""}" style="--pc:{PRI_HEX[t.priority.value]}"><div class="bar"></div><div class="body">'
                                f'<div class="t">{h(t.summary)}</div><div class="m"><span class="mono">{h(t.ticket_id)}</span>{cat_tag(t.category.value)}{status(t.status.value)}'
                                f'{("🚨 " + tag("CRITICAL SAFETY", "cr")) if t.critical_alert else ""}{sla_chip(sla.label(t, now), stt)}<span>{h(names.get(t.assignee_id, "Unassigned"))}</span>'
                                + (tag("Review", "v") if t.review_required and t.status in LIVE_STATUSES else "") + (tag("Linked", "b") if t.duplicate_of else "")
                                + (tag("Review withdrawal", "cr") if t.withdrawal_review else "")
                                + (tag("Sample") if t.is_sample else "") + '</div></div></div>', unsafe_allow_html=True)
                    cb.button("Open", key=f"open_{t.ticket_id}", on_click=select, args=(t.ticket_id,))
                if len(rows) > limit:
                    st.button(f"Show more ({len(rows) - limit} left)", key="more", on_click=lambda: st.session_state.update(limit=limit + 15))
                if not rows:
                    md('<div class="ph">Nothing in this queue.</div>')
                with st.expander("Bulk actions"):
                    picked = st.multiselect("Tickets", [t.ticket_id for t in rows], key="bulk_ids")
                    sure = st.checkbox("I confirm this change for every selected ticket", key="bulk_ok")
                    b1, b2 = st.columns(2)
                    for col, key, text, fn in ((b1, "bulk_me", "Assign to me", lambda ids: bulk_assign(ids, actor.id, actor=actor)),
                                              (b2, "bulk_prog", "Start work", lambda ids: bulk_status(ids, Status.IN_PROGRESS, actor=actor))):
                        if col.button(text, key=key, disabled=not (picked and sure)):
                            ok, failed = fn(picked)
                            st.session_state["flash"] = ("ok" if not failed else "err", f"{len(ok)} updated and verified." + (f" {len(failed)} could not be changed: " + "; ".join(f"{k} ({v})" for k, v in failed.items()) if failed else ""))
                            st.session_state["bulk_ids"] = []
                            st.rerun()
            with det:
                t = get_ticket(sel) if sel else None
                with st.container(key="panel_det"):
                    if not t:
                        md('<div class="ph">Select a ticket to work on it.</div>')
                    else:
                        stt, _ = sla.state(t, now)
                        live = t.status in LIVE_STATUSES
                        md('<div class="dh">' + f'<span class="id">{h(t.ticket_id)}</span> {status(t.status.value)} {pri(t.priority.value)} ' + cat_tag(t.category.value)
                           + (tag("CRITICAL SAFETY ALERT", "cr") if t.critical_alert else "")
                           + (tag("Needs review", "v") if t.review_required and live else "") + (tag("Sample") if t.is_sample else "") + (tag(f"Reopened {t.reopen_count}×", "cr") if t.reopen_count else "")
                           + (tag("Anonymous reporter", "b") if t.is_anonymous else "")
                           + (tag("Withdrawal review", "cr") if t.withdrawal_review else "")
                           + f'<div class="sum">{h(t.summary)}</div>' + sla_chip(sla.label(t, now), stt)
                           + f' <span style="color:#6F675F;font-size:13px">due {sla.due_at(t):%d %b %H:%M} UTC · {h(t.location or "no location")} · {h(names.get(t.assignee_id, "unassigned"))}</span></div>')
                        if t.is_anonymous:
                            md('<div class="anonymous-note"><b>Anonymous report</b><span>Reporter account details are withheld. Reply through ticket comments; avoid asking for identifying information.</span></div>')
                        with st.expander("Routing details"):
                            st.caption("Suggested category, priority and department. You can correct these below.")
                            st.write("Suggested by the language model." if t.ai_mode == "llm" else "Assigned using the standard rules.")
                        md(f'<div class="sect"><div class="eyebrow">Original complaint</div>{h(t.description)}</div>')
                        with st.expander("Edit report details"):
                            edit_summary = st.text_input("Short summary", value=t.summary, max_chars=240, key=f"edit_summary_{sel}")
                            edit_description = st.text_area("Description", value=t.description, max_chars=5000, key=f"edit_desc_{sel}")
                            edit_location = st.text_input("Location", value=t.location or "", max_chars=200, key=f"edit_loc_{sel}")
                            if st.button("Save report details", key=f"save_details_{sel}"):
                                try:
                                    update_ticket_details(sel, edit_summary, edit_description, edit_location, actor=actor)
                                    st.toast("Ticket details saved and verified.", icon="✅"); st.rerun()
                                except TicketError as e:
                                    st.error(str(e))
                        with st.container(key=f"phs_{sel}"):
                            show_photos(sel, actor)
                        md(f'<div class="sect"><div class="eyebrow">Suggested routing · staff can correct</div>'
                           f'{cat_tag(t.category.value)} {pri(t.priority.value)} {tag(t.department, "sl")}</div>')
                        try:
                            md('<div class="sect"><div class="eyebrow">Assignment</div></div>')
                            matching_staff = [u for u in staff_users if not u.department or u.department == t.department]
                            assignment_staff = matching_staff or staff_users
                            ids = [u.id for u in assignment_staff]
                            st.caption(f"Suggested responder role: {t.department}. The list prioritizes that team and all-department admins; other teams are shown only if no matching responder account exists.")
                            a1, a2, a3 = st.columns([2, 1, 1])
                            who = a1.selectbox("Assign to", ids, format_func=lambda i: names[i] + (" · Worker" if role_of[i] == "worker" else " · Staff admin") + (f" · {dept_of[i]}" if dept_of.get(i) else ""),
                                               index=ids.index(t.assignee_id) if t.assignee_id in ids else ids.index(actor.id) if actor.id in ids else 0, key=f"asg_{sel}", label_visibility="collapsed")
                            if a2.button("Assign", key=f"doasg_{sel}", disabled=t.status == Status.WITHDRAWN):
                                assign_ticket(sel, who, actor=actor); st.toast("Assignment saved and verified.", icon="✅"); st.rerun()
                            if t.assignee_id is not None and a3.button("Unassign", key=f"unasg_{sel}", disabled=t.status == Status.WITHDRAWN):
                                assign_ticket(sel, None, actor=actor); st.toast("Ticket unassigned.", icon="✅"); st.rerun()
                            if t.status in LIVE_STATUSES and not t.staff_removed:
                                with st.expander("Resolution deadline"):
                                    current_due = sla.due_at(t)
                                    if current_due.tzinfo is None:
                                        current_due = current_due.replace(tzinfo=timezone.utc)
                                    current_due = current_due.astimezone(timezone.utc)
                                    st.caption(f"Current target: {current_due:%d %b %Y, %H:%M UTC}. Extending the target requires a reason, which is added to the student-visible timeline.")
                                    du1, du2 = st.columns(2)
                                    target_day = du1.date_input("New due date (UTC)", value=current_due.date(), key=f"due_date_{sel}")
                                    target_time = du2.time_input("New due time (UTC)", value=current_due.time().replace(microsecond=0),
                                                                 step=timedelta(seconds=1), key=f"due_time_{sel}")
                                    due_reason = st.text_area("Reason for extension", key=f"due_reason_{sel}", max_chars=500,
                                                              placeholder="Required only when moving the deadline later.", height=75)
                                    next_due = datetime.combine(target_day, target_time, tzinfo=timezone.utc)
                                    extension_needs_reason = next_due > current_due
                                    disabled = (next_due == current_due or next_due <= now or
                                                (extension_needs_reason and len((due_reason or "").strip()) < 5))
                                    if st.button("Save resolution deadline", key=f"save_due_{sel}", disabled=disabled):
                                        try:
                                            updated = update_deadline(sel, next_due, due_reason, actor=actor)
                                            label = sla.due_at(updated).strftime("%d %b %Y, %H:%M UTC")
                                            st.toast(f"Resolution deadline updated to {label}.", icon="✅")
                                            st.rerun()
                                        except TicketError as e:
                                            st.error(str(e))
                            md('<div class="sect"><div class="eyebrow">Status</div></div>')
                            if t.status == Status.REOPENED:
                                md('<div class="callout bad"><b>The student says this is not fixed.</b> The reason is in the timeline below.</div>')
                            if t.status in (Status.OPEN, Status.REOPENED):
                                s1, s2 = st.columns(2)
                                if s1.button("Start work", type="primary", key=f"start_{sel}"):
                                    update_status(sel, Status.IN_PROGRESS, actor=actor); st.toast("Work started. Verified.", icon="✅"); st.rerun()
                                s2.button("Mark as fixed…", key=f"fix_{sel}", on_click=open_modal, args=("fix",), kwargs={"tid": sel})
                            elif t.status == Status.IN_PROGRESS:
                                st.button("Mark as fixed…", type="primary", key=f"fix_{sel}", on_click=open_modal, args=("fix",), kwargs={"tid": sel})
                            elif t.status == Status.PENDING:
                                waited = (now - t.fixed_at).total_seconds() / 86400 if t.fixed_at else 0
                                md(f'<div class="callout wait"><b>Waiting for the student to confirm</b> ({waited:.1f} day{"s" if waited != 1 else ""}).<br>Fix note: {h(t.resolution_note or "")}</div>')
                                if waited >= settings.signoff_days:
                                    st.button("Close without confirmation…", key=f"close_{sel}", on_click=open_modal, args=("close_timeout",), kwargs={"tid": sel})
                                else:
                                    st.caption(f"The student has {settings.signoff_days - waited:.1f} more day(s) to answer before staff can close it.")
                            elif t.staff_removed:
                                md(f'<div class="callout bad"><b>Removed from active work.</b> The student can see this notice and the reason. The ticket history and attachments are retained.<br>Reason: {h(t.staff_removal_reason or "Not recorded")}</div>')
                            elif t.status == Status.WITHDRAWN:
                                md(f'<div class="callout wait"><b>Withdrawn by the student.</b> The report and its timeline are retained. Reason: {h(t.withdrawal_reason or "Not recorded")}'
                                   + ('<br><b>This report was flagged because of repeated withdrawals within seven days.</b>' if t.withdrawal_review else '') + '</div>')
                            else:
                                by = {"student": "confirmed by the student", "staff_timeout": "closed by staff after no reply"}.get(t.resolved_by or "", "closed")
                                md(f'<div class="callout ok"><b>Resolved</b>, {by}.' + (f" Rating {t.rating}/5." if t.rating else "") + f'<br>Fix note: {h(t.resolution_note or "none")}</div>')
                            cands = find_candidates(t.description, t.location, [x for x in tickets if x.ticket_id != sel], settings.dup_threshold)
                            if t.duplicate_of or (cands and live):
                                md('<div class="sect"><div class="eyebrow">Duplicates</div></div>')
                            if t.duplicate_of:
                                md(f'{tag("Linked to " + t.duplicate_of, "b")}')
                                if st.button("Remove link", key=f"ul{sel}"):
                                    set_duplicate_link(sel, None, actor=actor); st.toast("Link removed.", icon="✅"); st.rerun()
                            for c in ([] if t.duplicate_of or not live else cands):
                                md(f'<div class="dupc"><b>Possible duplicate of {h(c.ticket_id)}</b> {tag(c.status.value, "o")}<p>{h(c.summary)}</p><small>Similarity {c.score:.0f}/100. {h(c.evidence)}</small></div>')
                                if st.button(f"Link to {c.ticket_id}", key=f"lk_{sel}_{c.ticket_id}"):
                                    set_duplicate_link(sel, c.ticket_id, actor=actor); st.toast("Link saved and verified.", icon="✅"); st.rerun()
                            with st.expander("Correct or re-route"):
                                cl = [c_.value for c_ in Category]; pl = [p_.value for p_ in Priority]
                                nc = st.selectbox("Category", cl, index=cl.index(t.category.value), key=f"c{sel}")
                                np_ = st.selectbox("Priority", pl, index=pl.index(t.priority.value), key=f"p{sel}")
                                nd = st.selectbox("Department", DEPARTMENTS, index=DEPARTMENTS.index(t.department) if t.department in DEPARTMENTS else 0, key=f"d{sel}")
                                if st.button("Save changes", key=f"sv{sel}"):
                                    correct_fields(sel, Category(nc), Priority(np_), nd, actor=actor)
                                    st.toast("Saved and verified.", icon="✅"); st.rerun()
                            if not t.staff_removed:
                                with st.expander("Remove from active workspace"):
                                    st.warning("This removes the ticket from active work. The student will see your reason in Track a ticket; the ticket, comments, timeline, and attachments stay in the record.")
                                    removal_reason = st.text_area("Reason shown to the student", key=f"remove_reason_{sel}", max_chars=500,
                                                                  placeholder="Explain why this report is being removed.", height=85)
                                    confirm_delete = st.checkbox("I confirm this should be removed from active work", key=f"confirm_delete_{sel}")
                                    if st.button("Remove ticket and notify student", key=f"delete_{sel}", type="primary",
                                                 disabled=not (confirm_delete and len((removal_reason or "").strip()) >= 5)):
                                        delete_ticket(sel, removal_reason, actor=actor)
                                        st.session_state.pop("sel", None)
                                        st.session_state["flash"] = ("ok", f"Ticket {sel} was removed. Its history was retained and the student can see your notice in Track a ticket.")
                                        st.rerun()
                            md('<div class="sect"><div class="eyebrow">Add a note</div></div>')
                            render_voice_dictation(target_key=f"nt{sel}", key=f"staff_note_voice_{sel}", user_id=actor.id)
                            st.text_area("Note", key=f"nt{sel}", height=80, label_visibility="collapsed", placeholder="Write a note")
                            n1, n2 = st.columns([2, 1])
                            n1.radio("Who can see this", ["Internal (staff only)", "Visible to the student"], key=f"nv{sel}", horizontal=True, label_visibility="collapsed")
                            n2.button("Save note", key=f"addnote{sel}", on_click=save_note, args=(sel,))
                            md('<div class="sect"><div class="eyebrow">Timeline</div></div>')
                            md(_timeline(get_timeline(sel, actor=actor)))
                        except (TicketError, KeyError) as e:
                            st.error(str(e))

    # ------------------------------------------------------------ OVERVIEW
    with t_ov:
        m = metrics.compute(actor=actor)
        if not m["total"]:
            st.info("Charts and metrics appear once tickets exist. Nothing here is estimated.")
        else:
            fmt = lambda v, u: "n/a" if v is None else f"{v}{u}"
            md('<div class="kpis">' + kpi("Open", m["open"], "#2F6FED") + kpi("In progress", m["in_progress"], "#D98E04") + kpi("Waiting for student", m["pending"], "#7A5AF8")
               + kpi("Reopened", m["reopened"], "#E4572E") + kpi("Overdue", m["overdue"], "#B93A16") + kpi("Resolved", m["resolved"], "#2E9E5B") + "</div>")
            md('<div class="kpis four">' + kpi("Median time to fix", fmt(m["median_fix_hours"], " h"), "#F97C3C") + kpi("Median first response", fmt(m["median_first_response_hours"], " h"), "#2F6FED")
               + kpi("Reopen rate", fmt(m["reopen_rate"], "%"), "#E4572E") + kpi(f"Satisfaction ({m['rating_count']} ratings)", fmt(m["avg_rating"], " / 5"), "#2E9E5B") + "</div>")
            st.caption(f"Time to fix = submission to the moment staff mark it fixed (median). First response = submission to the first staff action. Reopen rate = fixed or closed tickets a student reopened. "
                       f"Fixed within target uses {settings.sla_high_hours:g}h / {settings.sla_medium_hours:g}h / {settings.sla_low_hours:g}h for High / Medium / Low: {fmt(m['sla_compliance'], '%')}. n/a means not enough data yet.")
            a = counts(tickets)
            c1, c2 = st.columns(2, gap="medium")
            with c1.container(key="panel_c1"):
                md('<div class="d3">By category</div>')
                fig = px.bar(a["category"], x="Tickets", y="Category", orientation="h", color="Category", color_discrete_map=CAT_HEX)
                st.plotly_chart(style_fig(fig).update_yaxes(categoryorder="array", categoryarray=[c_.value for c_ in Category][::-1]), width="stretch", theme=None, config={"displayModeBar": False})
            with c2.container(key="panel_c2"):
                md('<div class="d3">By status</div>')
                st.plotly_chart(style_fig(px.bar(a["status"], x="Status", y="Tickets", color="Status", color_discrete_map=STATUS_HEX)), width="stretch", theme=None, config={"displayModeBar": False})
            c3, c4 = st.columns(2, gap="medium")
            with c3.container(key="panel_c3"):
                md('<div class="d3">Complaint volume, last 14 days</div>')
                vol = pd.DataFrame(m["volume_14d"], columns=["Day", "Tickets"])
                st.plotly_chart(style_fig(px.area(vol, x="Day", y="Tickets"), "#2F6FED"), width="stretch", theme=None, config={"displayModeBar": False})
            with c4.container(key="panel_c4"):
                md('<div class="d3">Priority mix and recurring places</div>')
                total = max(1, len(tickets))
                segs = [(p_, sum(t.priority.value == p_ for t in tickets)) for p_ in ("High", "Medium", "Low")]
                md('<div class="stack">' + "".join(f'<i style="width:{n / total * 100:.1f}%;background:{PRI_HEX[p_]}"></i>' for p_, n in segs) + '</div><div class="legend">'
                   + "".join(f'<span><span class="dot" style="background:{PRI_HEX[p_]}"></span>{p_} <b>{n}</b></span>' for p_, n in segs) + "</div>")
                md('<div class="eyebrow" style="margin:18px 0 8px">Locations reported most</div><div class="hl">'
                   + ("".join(f"<div>{h(loc)}</div><div>{n}</div>" for loc, n in m["top_locations"]) or "<div>No locations recorded yet</div><div></div>") + "</div>")

    # ------------------------------------------------------------ SYSTEM
    with t_sys:
        hc = health_check()
        md('<div class="eyebrow" style="margin-bottom:8px">Health</div>' + tag("Database reachable" if hc["ok"] else "Database problem", "gn" if hc["ok"] else "cr")
           + tag(f'Schema v{hc.get("schema_version", "?")}', "b") + tag("AI configured" if hc["ai_configured"] else "AI not configured", "gn" if hc["ai_configured"] else "cr")
           + tag(f'{hc.get("staff_accounts", 0)} admins · {hc.get("worker_accounts", 0)} workers · {hc.get("student_accounts", 0)} students', "sl") + (tag("Demo mode on", "cr") if settings.demo_mode else ""))
        for issue in hc["issues"]:
            st.warning(issue)
        e1, e2 = st.columns(2, gap="medium")
        with e1.container(key="panel_sys1"):
            md('<div class="d3">AI and limits</div>')
            llm, fb = sum(t.ai_mode == "llm" for t in tickets), sum(t.ai_mode == "fallback" for t in tickets)
            md(f'<div class="hl"><div>Provider</div><div>{h(urlparse(settings.base_url).hostname or "unknown")}</div><div>Model</div><div>{h(settings.model)}</div>'
               f'<div>Tickets analysed by the model</div><div>{llm}</div><div>Tickets that used fallback rules</div><div>{fb}</div>'
               f'<div>Analyses per student per hour</div><div>{settings.rate_analyses_per_hour}</div><div>Reports per student per day</div><div>{settings.rate_reports_per_day}</div>'
               f'<div>Days before staff may close an unanswered fix</div><div>{settings.signoff_days:g}</div></div>')
            md('<p class="note">A high fallback count means the AI service was unavailable or not configured. Those tickets are flagged for review.</p>')
            mail_ready = bool(settings.alert_smtp_host and settings.alert_email_from)
            st.caption("Critical device email alerts: configured" if mail_ready else "Critical device email alerts: not configured (the live safety queue still updates while staff are online).")
            sms_ready = bool(settings.twilio_account_sid and settings.twilio_auth_token and (settings.twilio_messaging_service_sid or settings.twilio_from_phone))
            safety_contacts = [w for w in list_worker_contacts(actor=actor) if w["department"] == SAFETY_DEPARTMENT and w["phone"] and not w["is_demo"]]
            st.caption(f"Critical safety SMS: {'configured' if sms_ready else 'not configured'} · {len(safety_contacts)} real responder contact(s) available.")
            st.caption("Create responders with an occupation using create_user.py worker --occupation or the Create a worker account panel. Staff admins without a department receive every safety alert.")
        with e2.container(key="panel_sys2"):
            md('<div class="d3">Needs manual attention</div>')
            flagged = [t for t in tickets if (t.review_required and t.status in LIVE_STATUSES) or t.status == Status.REOPENED or t.withdrawal_review]
            md("".join(f'<p style="margin:0 0 6px"><span class="mono">{h(t.ticket_id)}</span> {h(t.summary)} {tag("Withdrawal review" if t.withdrawal_review else t.status.value if t.status == Status.REOPENED else t.ai_mode, "cr" if t.status == Status.REOPENED or t.withdrawal_review else "sl")}</p>' for t in flagged[:8]) or "<p>Nothing is waiting on a manual check.</p>")
        with st.expander("Staff accounts"):
            md('<div class="hl">' + "".join(f"<div>{h(u.name)} · {h(u.role.title())}</div><div>{h(u.department or 'All departments')} · {h(u.email)}</div>" for u in staff_users) + "</div>")
        with st.expander("Create a worker account"):
            with st.form("create_worker_form"):
                worker_name = st.text_input("Worker name", max_chars=80)
                worker_email = st.text_input("Worker email", max_chars=120)
                worker_occupation = st.selectbox("Occupation / response team", DEPARTMENTS)
                worker_password = st.text_input("Temporary password (at least 8 characters)", type="password")
                worker_password2 = st.text_input("Repeat temporary password", type="password")
                worker_phone = st.text_input("Worker SMS contact (international format)", value=settings.default_worker_phone,
                                             help="Used for critical safety SMS only when SMS provider credentials are configured.")
                make_worker = st.form_submit_button("Create worker login", type="primary")
            if make_worker:
                if worker_password != worker_password2:
                    st.error("The passwords do not match.")
                else:
                    try:
                        created_worker = create_worker(worker_name, worker_email, worker_password, worker_occupation, phone=worker_phone)
                        st.session_state["worker_created_notice"] = f"Worker account created for {created_worker.name} · {created_worker.department}. Share the login details securely."
                        st.rerun()
                    except AuthError as e:
                        st.error(str(e))
            if st.session_state.get("worker_created_notice"):
                st.success(st.session_state.pop("worker_created_notice"))
        with st.expander("Edit or remove a worker account"):
            account_notice = st.session_state.pop("worker_account_notice", None)
            if account_notice:
                st.success(account_notice)
            if worker_accounts:
                labels = {f"{w['name']} · {w['department']} · {w['email']}" + (" · Removed" if not w["is_active"] else ""): w for w in worker_accounts}
                selected_label = st.selectbox("Worker account", list(labels), key="worker_account_manage_select")
                account = labels[selected_label]
                if account["is_active"]:
                    wid = account["id"]
                    st.caption("Changing the occupation releases active assignments if they no longer match the worker’s team. Saving account changes signs the worker out everywhere.")
                    with st.form(f"edit_worker_account_{wid}"):
                        edit_name = st.text_input("Name", value=account["name"], key=f"edit_worker_name_{wid}")
                        edit_email = st.text_input("Email", value=account["email"], key=f"edit_worker_email_{wid}")
                        edit_team = st.selectbox("Occupation / response team", DEPARTMENTS,
                                                 index=DEPARTMENTS.index(account["department"]) if account["department"] in DEPARTMENTS else 0,
                                                 key=f"edit_worker_team_{wid}")
                        edit_phone = st.text_input("SMS contact", value=account["phone"] or "", key=f"edit_worker_phone_{wid}")
                        edit_password = st.text_input("New password (leave blank to keep current)", type="password", key=f"edit_worker_password_{wid}")
                        edit_password_confirm = st.text_input("Repeat new password", type="password", key=f"edit_worker_password2_{wid}")
                        save_worker = st.form_submit_button("Save worker account", type="primary")
                    if save_worker:
                        if edit_password != edit_password_confirm:
                            st.error("The new passwords do not match.")
                        else:
                            try:
                                update_worker_account(wid, edit_name, edit_email, edit_team, edit_phone,
                                                      new_password=edit_password or None, actor=actor)
                                st.session_state["worker_account_notice"] = "Worker account updated. The worker must sign in again."
                                st.rerun()
                            except AuthError as e:
                                st.error(str(e))
                    st.warning("Removing disables this login, clears its SMS contact, and releases active tickets to the team. Ticket history and the worker’s audit identity are retained.")
                    confirm_remove = st.checkbox("I confirm this worker account should be removed", key=f"confirm_remove_worker_{wid}")
                    if st.button("Remove worker account", key=f"remove_worker_{wid}", type="primary", disabled=not confirm_remove):
                        try:
                            released = delete_worker_account(wid, actor=actor)
                            st.session_state["worker_account_notice"] = f"Worker login removed. {released} active assignment(s) returned to the team."
                            st.rerun()
                        except AuthError as e:
                            st.error(str(e))
                else:
                    st.info("This worker login has been removed. The account record remains so existing tickets and audit history stay intact.")
            else:
                st.caption("No worker accounts yet.")
        with st.expander("Help a student or worker reset their password"):
            st.text_input("Student or worker email", key="rc_email")
            if st.button("Create one-time code", key="rc_issue"):
                try:
                    st.session_state["rc_code"] = (st.session_state.get("rc_email", ""), issue_reset_code(st.session_state.get("rc_email", ""), actor=actor))
                except AuthError as e:
                    st.session_state.pop("rc_code", None)
                    st.error(str(e))
            _rc = st.session_state.get("rc_code")
            if _rc:
                st.code(_rc[1])
                st.caption(f"For {_rc[0]}. Valid for 30 minutes and works once. Give it to the student in person.")
        st.download_button("Download all tickets (CSV)", to_csv(tickets), file_name="resolveai_tickets.csv", mime="text/csv", key="dl",
                           help="Spreadsheet formulas are neutralised. Photos are not included. Also run python backup.py on a schedule.")
