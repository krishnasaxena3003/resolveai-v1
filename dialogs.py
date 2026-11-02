"""Pop-up dialogs. Each is opened by setting session_state['modal'] and is re-drawn on every run until it is closed.
Buttons inside a dialog only re-run the dialog, so every action ends with close_modal() and st.rerun() (a full page run);
navigation requested from a dialog is queued with go_later()."""
import streamlit as st
from attachments import AttachmentError, save_image
from config import get_settings
from shared import PAGES, current_user, go_later
from ticket_service import TicketError, close_unconfirmed, get_ticket, mark_fixed, student_resolve, student_signoff
from ui import cat_tag, h, md, pri, status, tag, terminal
from voice_ui import render_voice_dictation

PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]


def open_modal(kind, **kw):
    st.session_state["modal"] = {"kind": kind, **kw}


def close_modal():
    st.session_state.pop("modal", None)


def _save_photos(files, ticket_id, kind, uploader_id):
    bad = []
    for f in files or []:
        try:
            save_image(ticket_id, f.getvalue(), f.name, kind=kind, uploader_id=uploader_id)
        except AttachmentError as e:
            bad.append(f"{f.name}: {e}")
    return bad


def _head(t):
    md(f'<div class="dh"><span class="id">{h(t.ticket_id)}</span> {status(t.status.value)} {pri(t.priority.value)} {cat_tag(t.category.value)}<div class="sum" style="font-size:22px">{h(t.summary)}</div></div>')


@st.dialog("Mark as fixed", on_dismiss=close_modal)
def dlg_fix(m):
    t, actor = get_ticket(m["tid"]), current_user()
    _head(t)
    st.caption("The student will be asked to confirm. Describe what was done so they can verify it.")
    render_voice_dictation(target_key="fx_note", key=f"fix_voice_{t.ticket_id}", user_id=actor.id)
    note = st.text_area("What was done?", key="fx_note", height=110, placeholder="e.g. Replaced the faulty fuse and tested the circuit")
    photo = st.file_uploader("Required: add a repair photo", type=PHOTO_TYPES, key="fx_photo")
    if not photo:
        st.caption("Attach one photo and describe at least 10 characters of work before the student is asked to confirm.")
    c1, c2 = st.columns(2)
    if c1.button("Mark fixed and ask the student", type="primary", key="fx_go",
                 disabled=not photo or len((note or "").strip()) < 10):
        try:
            if not photo:
                raise AttachmentError("Add at least one repair photo before asking the student to verify the fix.")
            from attachments import validate_image
            validate_image(photo.getvalue())
            save_image(t.ticket_id, photo.getvalue(), photo.name, kind="resolution", uploader_id=actor.id)
            mark_fixed(t.ticket_id, note, actor=actor)
            st.session_state["flash"] = ("ok", "Repair photo saved. The student has been asked to verify the fix.")
            close_modal(); st.rerun()
        except (TicketError, AttachmentError) as e:
            st.error(str(e))
    if c2.button("Cancel", key="fx_cancel"):
        close_modal(); st.rerun()


@st.dialog("Close without confirmation", on_dismiss=close_modal)
def dlg_close_timeout(m):
    t, actor = get_ticket(m["tid"]), current_user()
    _head(t)
    st.warning(f"The student has not answered for {get_settings().signoff_days:g} days or more. Closing records that staff closed this ticket without the student's confirmation.")
    c1, c2 = st.columns(2)
    if c1.button("Close the ticket", type="primary", key="ct_go"):
        try:
            close_unconfirmed(t.ticket_id, actor=actor)
            st.session_state["flash"] = ("ok", "Ticket closed. It is marked as closed by staff without the student's confirmation.")
            close_modal(); st.rerun()
        except TicketError as e:
            st.error(str(e))
    if c2.button("Cancel", key="ct_cancel"):
        close_modal(); st.rerun()


@st.dialog("Is it fixed?", on_dismiss=close_modal)
def dlg_signoff(m):
    t, actor = get_ticket(m["tid"]), current_user()
    _head(t)
    md(f'<div class="callout wait"><b>The team says it is fixed:</b><br>{h(t.resolution_note or "No description given")}</div>')
    st.markdown('<div class="rating-card"><div class="rating-kicker">YOUR FEEDBACK</div><div class="rating-prompt">How was the repair?</div><div class="rating-sub">Rate the campus team’s work from 1 to 5 stars.</div></div>', unsafe_allow_html=True)
    rating = st.radio("Choose a rating", [1, 2, 3, 4, 5], index=None,
                      format_func=lambda v: "★" * v, horizontal=True, key="so_rating_v2", label_visibility="collapsed")
    labels = {1: "Poor", 2: "Needs improvement", 3: "Good", 4: "Very good", 5: "Excellent"}
    if rating:
        st.caption(f"{rating} out of 5 · {labels[rating]}")
    comment = st.text_area("Anything to add? (optional)", key="so_comment", height=80)
    c1, c2 = st.columns(2)
    if c1.button("Submit rating & confirm fix", type="primary", key="so_go", disabled=rating is None):
        try:
            student_signoff(t.ticket_id, actor=actor, confirm=True, comment=comment, rating=rating or None)
            st.session_state["flash"] = ("ok", "Thank you. The ticket is closed.")
            st.session_state["confetti"] = True
            close_modal(); st.rerun()
        except TicketError as e:
            st.error(str(e))
    if c2.button("Not yet", key="so_cancel"):
        close_modal(); st.rerun()


@st.dialog("Not fixed? Tell us what is wrong", on_dismiss=close_modal)
def dlg_reopen(m):
    t, actor = get_ticket(m["tid"]), current_user()
    _head(t)
    reason = st.text_area("What is still wrong?", key="ro_reason", height=100, placeholder="e.g. The lights on the second floor are still off")
    files = st.file_uploader("A new photo helps (optional)", type=PHOTO_TYPES, accept_multiple_files=True, key="ro_photos")
    c1, c2 = st.columns(2)
    if c1.button("Reopen the ticket", type="primary", key="ro_go"):
        try:
            student_signoff(t.ticket_id, actor=actor, confirm=False, comment=reason)
            bad = _save_photos(files, t.ticket_id, "report", actor.id)
            st.session_state["flash"] = ("ok" if not bad else "err", "Reopened. The team has been told." + (" Photos not saved: " + "; ".join(bad) if bad else ""))
            close_modal(); st.rerun()
        except TicketError as e:
            st.error(str(e))
    if c2.button("Cancel", key="ro_cancel"):
        close_modal(); st.rerun()


@st.dialog("Mark as resolved?", on_dismiss=close_modal)
def dlg_resolve_own(m):
    t, actor = get_ticket(m["tid"]), current_user()
    _head(t)
    st.caption("Use this if the problem has gone away or you fixed it yourself. The team will see that you closed it.")
    note = st.text_input("What happened? (optional)", key="own_note", max_chars=300)
    c1, c2 = st.columns(2)
    if c1.button("Yes, mark as resolved", type="primary", key="own_go"):
        try:
            student_resolve(t.ticket_id, note, actor=actor)
            st.session_state["flash"] = ("ok", "Ticket resolved.")
            st.session_state["confetti"] = True
            close_modal(); st.rerun()
        except TicketError as e:
            st.error(str(e))
    if c2.button("Cancel", key="own_cancel"):
        close_modal(); st.rerun()


@st.dialog("Report submitted", on_dismiss=close_modal)
def dlg_submitted(m):
    md(f'{tag("Saved and verified", "g")}<div class="idbig">{h(m["tid"])}</div>')
    st.markdown(f"**Tracking code:** `{m['code']}`")
    if m.get("photos"):
        st.caption(f"{m['photos']} photo(s) attached.")
    if m.get("bad"):
        st.warning("Some photos were not saved: " + "; ".join(m["bad"]))
    md('<p class="note">Your report is listed under Track a ticket. Keep the ID and code in case you need to look it up on another device.</p>')
    c1, c2 = st.columns(2)
    if c1.button("Track my report", type="primary", key="sub_track"):
        close_modal(); go_later(PAGES[2]); st.rerun()
    if c2.button("Close", key="sub_close"):
        close_modal(); st.rerun()


@st.dialog("How ResolveAI handled this report", width="large", on_dismiss=close_modal)
def dlg_pipeline(m):
    t = get_ticket(m["tid"])
    llm = t.ai_mode == "llm"
    lines = [("ok", f"[1/4] Input received · {len(t.description)} characters"),
             ("ok" if llm else "warn", "[2/4] AI analysis · " + ("language model" if llm else "fallback rules (the AI was unavailable or not configured)")),
             ("ok", f"[3/4] Output validated · {h(t.category.value)} · {h(t.priority.value)} priority · routed to {h(t.department)}"),
             ("info", "[4/4] Duplicate check · " + (f"linked to {h(t.duplicate_of)}" if t.duplicate_of else "no link recorded")),
             ("ok", "[✓] Saved and read back before the reference was issued")]
    md(terminal("Pipeline for " + t.ticket_id, lines))
    if t.review_required:
        st.caption("This ticket was flagged for a human check: it is High priority or the AI could not be used.")
    if st.button("Close", key="pipe_close"):
        close_modal(); st.rerun()


_DIALOGS = {"fix": dlg_fix, "close_timeout": dlg_close_timeout, "signoff": dlg_signoff, "reopen": dlg_reopen, "resolve_own": dlg_resolve_own,
            "submitted": dlg_submitted, "pipeline": dlg_pipeline}


def render_modal():
    m = st.session_state.get("modal")
    if m and m["kind"] in _DIALOGS:
        _DIALOGS[m["kind"]](m)
