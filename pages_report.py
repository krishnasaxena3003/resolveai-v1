import streamlit as st
from attachments import MAX_BYTES, MAX_FILES, AttachmentError, save_image, validate_image
from campus_catalog import LOCATIONS
from config import get_settings
from dialogs import PHOTO_TYPES, open_modal
from duplicate_service import find_candidates
from rate_limit import RateLimitError, check as rate_check
from shared import PAGES, go, require
from sample_data import SAMPLE_REPORTS
from safety_alerts import email_staff_critical_alert, is_critical_hazard, sms_safety_workers_critical_alert
from ticket_service import TicketError, list_tickets
from ui import cat_tag, h, md, pri, tag, terminal
from voice_service import SPEECH_LANGUAGES, VoiceError, transcribe_audio, validate_audio
from workflow import InputError, finalize_submission, prepare_submission

OTHER, CHOOSE = "Other…", "Choose a location…"


def _steps(current):
    names = ["Speak or type", "Review", "Submitted"]
    return '<ol class="stp" style="max-width:420px;margin:0 0 18px">' + "".join(f'<li class="{"done" if i < current else "cur" if i == current else ""}"><i></i>{n}</li>' for i, n in enumerate(names)) + "</ol>"


def _report_head(title, lead):
    md('<section class="campus-page-banner"><div class="eyebrow">Report an issue</div>'
       + f'<div class="pgh" role="heading" aria-level="1">{h(title)}</div><p class="lead">{h(lead)}</p></section>')


def _discard_voice():
    transcript = st.session_state.pop("voice_transcript", None)
    if transcript and st.session_state.get("desc") == transcript:
        st.session_state["desc"] = ""
    st.session_state.pop("voice_audio", None)
    st.session_state.pop("voice_upload", None)


def _new_report():
    for key in ("created", "created_photos", "critical_delivery", "critical_sms_delivery", "prepared", "prepared_files", "voice_audio", "voice_upload", "voice_transcript", "desc", "photos", "loc_sel", "loc_other"):
        st.session_state.pop(key, None)


def _location():
    sel = st.session_state.get("loc_sel", CHOOSE)
    return (st.session_state.get("loc_other", "") if sel == OTHER else "" if sel == CHOOSE else sel).strip()


def _location_options(settings):
    from database import connect
    with connect() as conn:
        rows = conn.execute("SELECT location_id,display_name FROM campus_locations ORDER BY display_name").fetchall()
    names = {r["display_name"]: r["location_id"] for r in rows}
    names.update({name: None for name in settings.campus_locations if name not in names})
    return names


def _submit(p, user, files, link_to=None):
    """Rate-limited, verified save, then the photos. A photo problem never undoes a saved ticket."""
    s = get_settings()
    files = list(files or [])
    if not files:
        raise AttachmentError("Attach at least one photo of the issue before submitting.")
    if len(files) > MAX_FILES:
        raise AttachmentError(f"Attach no more than {MAX_FILES} photos.")
    for photo in files:
        validate_image(photo.getvalue())
    rate_check(user["id"], "report", s.rate_reports_per_day, 24 * 60)
    created = finalize_submission(p, link_to=link_to, reporter_id=user["id"],
                                  is_anonymous=bool(st.session_state.get("anonymous_report", False)))
    saved, bad = 0, []
    for f in (files or [])[:MAX_FILES]:
        try:
            save_image(created.ticket.ticket_id, f.getvalue(), f.name, kind="report", uploader_id=user["id"])
            saved += 1
        except AttachmentError as e:
            bad.append(f"{f.name}: {e}")
    sent, recipient_count, mail_configured = email_staff_critical_alert(created.ticket)
    st.session_state["critical_delivery"] = (sent, recipient_count, mail_configured) if created.ticket.critical_alert else None
    sms_sent, sms_recipients, sms_configured = sms_safety_workers_critical_alert(created.ticket)
    st.session_state["critical_sms_delivery"] = (sms_sent, sms_recipients, sms_configured) if created.ticket.critical_alert else None
    st.session_state["created"] = created
    st.session_state["created_photos"] = (saved, bad)
    st.session_state.pop("prepared", None)
    open_modal("submitted", tid=created.ticket.ticket_id, code=created.tracking_code, photos=saved, bad=bad)
    st.session_state["confetti"] = True
    st.rerun()


def render():
    s = get_settings()
    user = require("student", "Report an issue", "Students sign in to file a report, so you can follow it to resolution without a tracking code.")
    md(f'<section class="student-portal-banner"><div class="student-mark">S</div><div><div class="eyebrow">STUDENT PORTAL · NEW REQUEST</div><div class="student-banner-title">Report a campus issue</div><p>Your report stays connected to your account, so you can follow updates and respond to the team.</p></div><div class="student-banner-step">01 <span>REPORT</span></div></section>')
    if st.session_state.pop("clear_voice_audio_on_rerun", False):
        st.session_state.pop("voice_audio", None)
        st.session_state.pop("voice_upload", None)
    if not s.api_key:
        st.info("AI is not configured (no LLM_API_KEY). Reports will use clearly labelled fallback rules.")
    created = st.session_state.get("created")
    if created:
        t = created.ticket
        saved, bad = st.session_state.get("created_photos", (0, []))
        _report_head("Your report is saved.", "Your ticket is ready. Keep the reference and tracking code to follow progress.")
        md(_steps(3))
        with st.container(key="okpanel"):
            md(f'{tag("Saved and verified", "g")}<div class="idbig">{h(t.ticket_id)}</div>')
            st.markdown(f"**Tracking code:** `{created.tracking_code}`")
            if saved:
                st.caption(f"{saved} photo(s) attached. Location data in photos is removed.")
            if bad:
                st.warning("Some photos were not saved: " + "; ".join(bad))
            if t.duplicate_of:
                st.write(f"Your report was kept and linked to {t.duplicate_of}.")
            if t.is_anonymous:
                st.info("Submitted anonymously to campus staff. Your account stays privately linked so you can track and manage the report.")
        if t.critical_alert:
            st.error(f"Potential life-safety hazard: routed to Campus Safety & Emergency Response with a {get_settings().sla_critical_minutes:g}-minute response target. If anyone is in immediate danger, contact campus security or emergency services now; do not wait for a ticket update.")
            md('<p><a href="tel:112" style="display:inline-flex;min-height:44px;align-items:center;padding:9px 15px;border-radius:10px;background:#B42318;color:#fff;font-weight:700;text-decoration:none">Call emergency services · 112</a></p>')
            sent, total, configured = st.session_state.get("critical_delivery") or (0, 0, False)
            if sent:
                st.success(f"Device email alert sent to {sent} campus safety/admin account(s).")
            elif configured and total:
                st.warning("The ticket is in the live safety queue, but email delivery could not be confirmed. Contact campus security directly if there is immediate danger.")
            else:
                st.warning("The ticket is in the live safety queue. Device email alerts are not configured for this deployment; contact campus security directly if there is immediate danger.")
            sms_sent, sms_recipients, sms_configured = st.session_state.get("critical_sms_delivery") or (0, 0, False)
            if sms_sent:
                st.success(f"SMS alert accepted for {sms_sent} of {sms_recipients} Campus Safety responder(s).")
            elif sms_configured and sms_recipients:
                st.warning("SMS is configured, but delivery could not be confirmed. The live safety queue is updated.")
            elif sms_configured:
                st.info("SMS is configured, but no non-demo Campus Safety worker has a phone number yet.")
            else:
                st.info("SMS alerts are not configured for this deployment.")
        c1, c2 = st.columns(2)
        c1.button("Report another issue", key="again", on_click=_new_report)
        c2.button("See my reports", key="to_track", type="primary", on_click=go, args=(PAGES[2],))
        return
    p = st.session_state.get("prepared")
    _report_head("Tell us what’s wrong.", "Describe the problem in plain words, by voice or text. We’ll suggest where it should go, check for similar reports, and give you a ticket reference once it is saved.")
    md(_steps(1 if p else 0))

    def sample():
        for key in ("voice_audio", "voice_upload", "voice_transcript", "prepared", "prepared_files"):
            st.session_state.pop(key, None)
        chosen = st.session_state.get("sample_report_choice", SAMPLE_REPORTS[0][0])
        _, description, location = next((item for item in SAMPLE_REPORTS if item[0] == chosen), SAMPLE_REPORTS[0])
        st.session_state.update(desc=description, loc_sel=location, loc_other="")

    with st.container(key="voice_box"):
        md('<div class="voice-title">🎙️ Speak your complaint</div>'
           '<div class="voice-help">Record in your browser, then review the words before the AI check. Audio is sent for transcription only when you choose Transcribe; ResolveAI does not save the recording. If microphone access is blocked, allow it in your browser or upload a WAV below.</div>')
        language = st.selectbox("Spoken language", list(SPEECH_LANGUAGES), key="report_voice_language")
        audio = st.audio_input("Start recording", sample_rate=16000, key="voice_audio", disabled=not s.speech_api_key,
                               help="Allow microphone access when your browser asks. Stop recording when you are done.")
        uploaded_audio = st.file_uploader("Or upload a WAV recording", type=["wav"], key="voice_upload", disabled=not s.speech_api_key,
                                          help="Use this if your browser or device cannot record from the microphone.")
        if audio is None:
            audio = uploaded_audio
        if not s.speech_api_key:
            st.caption("Voice transcription is not configured. Set SPEECH_API_KEY or LLM_API_KEY to enable it, or type your report below.")
        if audio is not None:
            audio_data = audio.getvalue()
            try:
                audio_info = validate_audio(audio_data, settings=s)
                st.caption(f"Recording ready · {audio_info.duration_seconds:.0f} sec · {audio_info.size_bytes / (1024 * 1024):.1f} MB")
                st.audio(audio_data, format="audio/wav")
                c_transcribe, c_discard = st.columns([1.25, 1])
                if c_transcribe.button("Transcribe audio", type="primary", key="transcribe_audio", disabled=not s.speech_api_key):
                    try:
                        rate_check(user["id"], "speech", s.rate_analyses_per_hour, 60)
                        with st.spinner("Transcribing your recording…"):
                            transcript = transcribe_audio(audio_data, language=SPEECH_LANGUAGES[language], settings=s)
                        st.session_state["desc"] = transcript
                        st.session_state["voice_transcript"] = transcript
                        st.session_state["clear_voice_audio_on_rerun"] = True
                        st.rerun()
                    except (VoiceError, RateLimitError) as e:
                        st.error(str(e))
                c_discard.button("Discard recording", key="discard_audio", on_click=_discard_voice)
            except VoiceError as e:
                st.error(str(e))
                st.button("Discard recording", key="discard_invalid_audio", on_click=_discard_voice)
        if st.session_state.get("voice_transcript"):
            md('<div class="voice-review"><b>Review your transcript before submitting.</b> Speech recognition can make mistakes. Edit the complaint text below, then continue through the regular AI review.</div>')

    left, right = st.columns(2, gap="large")
    with left:
        desc = st.text_area("What happened?", max_chars=1000, height=150, key="desc", placeholder="e.g. No electricity in Hostel Block B since morning")
        critical_preview = is_critical_hazard(desc)
        if critical_preview:
            st.error(f"Potential emergency hazard detected. This report will be routed to Campus Safety & Emergency Response with a {s.sla_critical_minutes:g}-minute target. For immediate danger, call campus security/emergency services now.")
        location_options = _location_options(s)
        options = list(location_options)
        st.selectbox("Where is it?", [CHOOSE, *options, OTHER], key="loc_sel")
        if st.session_state.get("loc_sel") == OTHER:
            st.text_input("Describe the location", key="loc_other", max_chars=80, placeholder="Building, floor or room")
        loc = _location()
        st.checkbox("Keep my identity anonymous from campus staff", key="anonymous_report",
                    help="Your account remains privately linked so you can track, comment on, and manage this report. Staff see it marked anonymous. Your description, location, or photos may still reveal who you are, so avoid names and identifying details if that matters to you.")
        st.caption("Anonymous reports remain linked to your account for secure follow-up. Staff can reply through the ticket without seeing your account name or email.")
        files = st.file_uploader(f"Required: add at least 1 photo (up to {MAX_FILES})", type=PHOTO_TYPES, accept_multiple_files=True, key="photos",
                                 help="At least one JPEG, PNG or WebP photo is required. Up to 5 MB each; photo metadata is removed.")
        files = list(files or [])
        problems = [f"{f.name} is over 5 MB" for f in files if f.size > MAX_BYTES] + ([f"Only the first {MAX_FILES} photos will be attached"] if len(files) > MAX_FILES else [])
        for pr in problems:
            st.warning(pr)
        if not files:
            st.warning("Add at least one photo of the issue to continue to ticket submission.")
        if files:
            cols = st.columns(min(3, len(files)))
            for i, f in enumerate(files[:MAX_FILES]):
                cols[i % len(cols)].image(f.getvalue(), width=110, caption=f.name[:18])
        if len((desc or "").strip()) >= 15:  # a quick, non-AI hint before the person spends an analysis
            hint = find_candidates(desc, loc, list_tickets(), s.dup_threshold, limit=1)
            if hint:
                md(f'<div class="dupc"><b>A similar report may already exist</b><p style="margin:4px 0">{h(hint[0].summary)}</p><small>You can still submit yours. We will show how they relate in the next step.</small></div>')
        a, b, _ = st.columns([1.5, 1, .3])
        if a.button("Run AI check →", type="primary", key="analyze", disabled=any("over 5 MB" in x for x in problems)):
            st.session_state.pop("prepared", None)
            try:
                with st.spinner("Analyzing your complaint…"):
                    if len((desc or "").strip()) >= 15:  # only real attempts count toward the AI budget
                        rate_check(user["id"], "analysis", s.rate_analyses_per_hour, 60)
                    st.session_state["prepared"] = prepare_submission(desc, loc, location_id=location_options.get(loc))
                    st.session_state["prepared_files"] = len(files[:MAX_FILES])
                    st.rerun()
            except (InputError, TicketError, RateLimitError) as e:
                st.error(str(e))
        b.selectbox("Example report", [item[0] for item in SAMPLE_REPORTS], key="sample_report_choice", label_visibility="collapsed")
        b.button("Use selected sample", key="sample", on_click=sample)
    with right:
        with st.container(key="panel_res"):
            if not p:
                md('<div class="ph">The AI check and duplicate search will appear here, step by step.</div>')
                return
            r, o = p.outcome.result, p.outcome
            llm = o.mode == "llm"
            best = p.candidates[0] if p.candidates else None
            md(terminal("Pipeline", [("ok", f"[1/4] Input validated · {len(p.description)} characters · {st.session_state.get('prepared_files', 0)} photo(s)"),
                                     ("ok" if llm else "warn", "[2/4] AI analysis · " + (f"{h(s.model)} · {o.latency_ms} ms · attempt {o.attempts}" if llm else f"fallback rules · {o.latency_ms} ms")),
                                     ("ok", f"[3/4] Output validated · {h(r.category.value)} · {h(r.priority.value)} · routed to {h(r.department)}"),
                                     ("info" if best else "ok", "[4/4] Duplicate check · " + (f"best match {h(best.ticket_id)} ({best.score:.0f}/100)" if best else "no likely duplicates"))]))
            md((tag("CRITICAL SAFETY ROUTE", "cr") if p.critical_alert else tag("Flagged for staff review", "o") if r.review_required else "") + '<div class="pgh" style="font-size:26px">Recommendation</div><dl class="out">'
               f'<dt>Summary</dt><dd>{h(r.summary)}</dd><dt>Category</dt><dd>{cat_tag(r.category.value)}</dd><dt>Priority</dt><dd>{pri(r.priority.value)}</dd>'
               f'<dt>Department</dt><dd>{h(r.department)}</dd><dt>Rationale</dt><dd style="font-weight:400">{h(r.rationale or "None given")}</dd></dl>'
               '<p class="note">These are recommendations. Staff can correct them.</p>')
            if o.warning:
                st.warning(o.warning)
            try:
                if p.candidates:
                    for i, c in enumerate(p.candidates):
                        md(f'<div class="dupc"><b>Possible duplicate: {h(c.ticket_id)}</b> {tag(c.status.value, "o")}<p>{h(c.summary)}</p>'
                           f'<small>Text similarity {c.score:.0f}/100 (illustrative, not proof of the same incident). {h(c.evidence)}</small></div>')
                        if st.button("Same issue: submit mine and link it", key=f"link{i}", disabled=not files or bool(problems)):
                            _submit(p, user, files, link_to=c.ticket_id)
                    if st.button("Different issue: submit as a new report", key="new_anyway", type="primary", disabled=not files or bool(problems)):
                        try:
                            _submit(p, user, files)
                        except AttachmentError as e:
                            st.error(str(e))
                else:
                    if st.button("Submit report", type="primary", key="create", disabled=not files or bool(problems)):
                        _submit(p, user, files)
            except (TicketError, RateLimitError, AttachmentError) as e:
                st.error(str(e))
