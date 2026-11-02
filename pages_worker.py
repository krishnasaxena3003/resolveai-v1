"""Occupation-scoped worker task board. Workers can only act on tasks they claim or are assigned."""
from datetime import datetime, timezone
from urllib.parse import quote_plus
import streamlit as st

import sla
from attachments import MAX_BYTES, AttachmentError, save_image
from schemas import LIVE_STATUSES, Status
from shared import current_user, require, show_photos
from ticket_service import (TicketError, add_comment, claim_worker_task, get_ticket, get_worker_timeline,
                            worker_list_tasks, update_status)
from ui import h, md, sla_chip, status, tag
from voice_ui import render_voice_dictation


def _campus_navigation(ticket=None):
    """Worker-safe campus map: shared location pins, with no cross-team incident counts."""
    from pages_campus import _data, _render_map
    from streamlit_folium import st_folium

    locations, _ = _data()
    counts = {}
    for loc in locations:
        counts[loc["display_name"]] = counts.get(loc["display_name"], 0) + 1
    by_label = {}
    for loc in locations:
        label = loc["display_name"] if counts[loc["display_name"]] == 1 else f"{loc['display_name']} · {loc['location_id']}"
        by_label[label] = loc
    location_match = None
    if ticket and ticket.location_id:
        location_match = next((loc for loc in locations if loc["location_id"] == ticket.location_id), None)
    if ticket and not location_match and ticket.location:
        location_match = next((loc for loc in locations if loc["display_name"].casefold().strip() == ticket.location.casefold().strip()), None)
    default_label = next((label for label, loc in by_label.items() if location_match and loc["location_id"] == location_match["location_id"]), "Campus overview")
    options = ["Campus overview", *by_label]
    options.insert(1, options.pop(options.index(default_label))) if default_label != "Campus overview" else None
    map_key = f"worker_map_focus_{ticket.ticket_id if ticket else 'overview'}"
    default_index = options.index(default_label)

    with st.expander("Campus map & directions", expanded=bool(ticket and ticket.location)):
        st.caption("Same AKGEC location map used by Campus Intelligence. Worker view shows campus locations only, not other teams’ reports.")
        focus_label = st.selectbox("Focus map on", options, index=default_index, key=map_key)
        focused = by_label.get(focus_label)
        st_folium(_render_map(locations, [], "Campus Locations", focused["location_id"] if focused else None,
                              catalog=locations, show_ticket_counts=False),
                  height=430, use_container_width=True, returned_objects=[])
        destination = ticket.location if ticket and ticket.location else focused["display_name"] if focused else "AKGEC, Ghaziabad"
        coordinates = False
        if ticket and ticket.location_id:
            exact = next((loc for loc in locations if loc["location_id"] == ticket.location_id), None)
            if exact and exact["latitude"] is not None and exact["longitude"] is not None:
                destination = f"{exact['latitude']},{exact['longitude']}"
                coordinates = True
        query = destination if coordinates else f"{destination}, AKGEC, Ghaziabad"
        directions = "https://www.google.com/maps/dir/?api=1&destination=" + quote_plus(query)
        st.link_button("Get directions in Google Maps ↗", directions, type="primary", use_container_width=True)
        if focused:
            st.caption(f"Map pin confidence: {focused['verification_status'].replace('_', ' ')}. Verify the exact room or entrance on arrival.")


def _timeline(items):
    return '<ul class="tl2">' + "".join(
        f'<li class="{h(item["kind"])}"><b>{h(item["who"])}</b> {h(item["text"])}'
        f'<small>{h(item["at"][:16].replace("T", " "))} UTC</small></li>'
        for item in reversed(items)) + "</ul>"


def render():
    worker_data = require("worker", "Worker workspace", "Workers sign in with the occupation assigned to their account.")
    actor = current_user()
    tasks = worker_list_tasks(actor=actor)
    now = datetime.now(timezone.utc)
    assigned = [t for t in tasks if t.assignee_id == actor.id]
    available = [t for t in tasks if t.assignee_id is None]
    awaiting = [t for t in assigned if t.status == Status.PENDING]
    critical = [t for t in tasks if t.critical_alert and t.status in LIVE_STATUSES]

    md('<section class="worker-hero"><div class="worker-icon">W</div><div class="worker-hero-copy">'
       f'<div class="eyebrow">FIELD OPERATIONS · {h(worker_data.get("department") or "TEAM")}</div>'
       '<div class="worker-title">My work board</div>'
       f'<p>Welcome, <b>{h(worker_data["name"])}</b>. Review your team tasks, record progress, and confirm completed work.</p>'
       '</div><div class="worker-role-badge">WORKER<br><b>ASSIGNED TEAM</b></div></section>')
    md('<div class="worker-metrics">'
       f'<div><b>{len(assigned) - len(awaiting)}</b><span>Active assignments</span></div><div><b>{len(available)}</b><span>Open team tasks</span></div>'
       f'<div><b>{len(awaiting)}</b><span>Awaiting student</span></div><div class="urgent"><b>{len(critical)}</b><span>Safety priority</span></div></div>')
    st.info("Work safely and follow campus procedures. Add a clear resolution note before marking work complete. For an immediate emergency, contact campus security/emergency services directly.")

    if not tasks:
        _campus_navigation()
        md('<div class="worker-empty"><b>No active tasks right now.</b><span>New work for your occupation will appear here. Ask a staff admin if you think a task is missing.</span></div>')
        return

    task_ids = [t.ticket_id for t in tasks]
    default_id = st.session_state.get("worker_ticket")
    if default_id not in task_ids:
        default_id = task_ids[0]
        st.session_state["worker_ticket"] = default_id
    chosen = st.selectbox("Choose a task", task_ids,
                          format_func=lambda tid: next((f'{t.summary} · {"Your task" if t.assignee_id == actor.id else "Available"}' for t in tasks if t.ticket_id == tid), tid),
                          key="worker_ticket")
    ticket = get_ticket(chosen)
    if not ticket:
        st.warning("This task is no longer available. Refresh the workspace.")
        return
    target = sla.due_at(ticket)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    else:
        target = target.astimezone(timezone.utc)
    remaining = sla.state(ticket, now)[0]
    md('<section class="worker-task-card">'
       f'<div class="worker-task-meta"><span>{h(ticket.ticket_id)}</span>{status(ticket.status.value)}'
       f'{tag(ticket.department, "b")}{tag("Critical safety", "cr") if ticket.critical_alert else ""}'
       f'<span class="worker-deadline">{sla_chip(sla.label(ticket, now), remaining)} · Due {target:%d %b, %H:%M UTC}</span></div>'
       f'<div class="worker-task-title">{h(ticket.summary)}</div>'
       f'<div class="worker-task-description">{h(ticket.description)}</div>'
       f'<div class="worker-task-location"><b>Location</b><span>{h(ticket.location or "Not provided")}</span>'
       f'<b>Team</b><span>{h(ticket.department)}</span><b>Priority</b><span>{h(ticket.priority.value)}</span></div></section>')
    _campus_navigation(ticket)

    if ticket.assignee_id is None:
        st.caption("This task is available to your occupation. Claim it before viewing evidence or updating its status.")
        if st.button("Claim this task", key=f"worker_claim_{ticket.ticket_id}", type="primary"):
            try:
                claim_worker_task(ticket.ticket_id, actor=actor)
                st.toast("Task claimed and assigned to you.", icon="✅")
                st.rerun()
            except TicketError as e:
                st.error(str(e))
        return
    if ticket.assignee_id != actor.id:
        st.warning("This task is assigned to another worker.")
        return

    if ticket.critical_alert:
        st.error("Potential safety incident: use the campus emergency procedure first. The ticket is not a replacement for direct emergency response.")
    show_photos(ticket.ticket_id, actor)
    controls = st.columns([1, 2])
    if ticket.status in (Status.OPEN, Status.REOPENED):
        if controls[0].button("Start work", type="primary", key=f"worker_start_{ticket.ticket_id}"):
            try:
                update_status(ticket.ticket_id, Status.IN_PROGRESS, actor=actor)
                st.toast("Task moved to In Progress.", icon="✅")
                st.rerun()
            except TicketError as e:
                st.error(str(e))
    if ticket.status in LIVE_STATUSES:
        with st.expander("Complete the task"):
            note_key = f"worker_fix_note_{ticket.ticket_id}"
            render_voice_dictation(target_key=note_key, key=f"worker_fix_voice_{ticket.ticket_id}", user_id=actor.id)
            resolution = st.text_area("What work was completed?", key=f"worker_fix_note_{ticket.ticket_id}", max_chars=1000,
                                      placeholder="Describe the repair or action so the student can verify it.")
            if len((resolution or "").strip()) < 10:
                st.caption("Add at least 10 characters explaining what was done.")
            evidence = st.file_uploader("Required: attach at least one repair photo", type=["jpg", "jpeg", "png", "webp"],
                                        key=f"worker_evidence_{ticket.ticket_id}", help="JPEG, PNG or WebP, up to 5 MB. Image metadata is removed.")
            if evidence and evidence.size > MAX_BYTES:
                st.warning("The image must be 5 MB or smaller.")
            if st.button("Send repair photo & ask student to verify", key=f"worker_complete_{ticket.ticket_id}", type="primary",
                         disabled=len((resolution or "").strip()) < 10 or evidence is None or evidence.size > MAX_BYTES):
                try:
                    save_image(ticket.ticket_id, evidence.getvalue(), evidence.name, kind="resolution", uploader_id=actor.id)
                    update_status(ticket.ticket_id, Status.PENDING, resolution, actor=actor)
                    st.toast("Repair photo saved. The student has been asked to verify the fix.", icon="✅")
                    st.rerun()
                except (TicketError, AttachmentError) as e:
                    st.error(str(e))

    with st.expander("Send an update to the student"):
        st.caption("This update is visible to the student and staff.")
        body = st.text_area("Work update", key=f"worker_comment_{ticket.ticket_id}", max_chars=1000,
                            placeholder="For example: I am checking the electrical panel now.")
        if st.button("Send update", key=f"worker_send_{ticket.ticket_id}", disabled=not (body or "").strip()):
            try:
                add_comment(ticket.ticket_id, body, "public", actor=actor)
                st.session_state[f"worker_comment_{ticket.ticket_id}"] = ""
                st.toast("Update sent to the student.", icon="✅")
                st.rerun()
            except TicketError as e:
                st.error(str(e))

    with st.expander("Task timeline"):
        md(_timeline(get_worker_timeline(ticket.ticket_id, actor=actor)))
