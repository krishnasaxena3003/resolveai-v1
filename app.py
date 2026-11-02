"""ResolveAI. This file only wires things together: configuration, navigation, the active page, dialogs and confetti."""
import os
import streamlit as st

try:  # Streamlit Cloud secrets -> environment (nothing hardcoded)
    for _k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "SPEECH_API_KEY", "SPEECH_BASE_URL", "SPEECH_MODEL", "SPEECH_TIMEOUT_SECONDS", "SPEECH_MAX_AUDIO_MB", "SPEECH_MAX_DURATION_SECONDS", "SPEECH_LANGUAGE", "DB_PATH", "UPLOAD_DIR", "DUP_THRESHOLD", "STAFF_EMAIL", "STAFF_PASSWORD", "ALLOWED_EMAIL_DOMAINS", "DEMO_MODE", "CAMPUS_LOCATIONS", "AGENT_MAX_TURNS", "AGENT_MAX_TOOL_CALLS", "AGENT_MAX_TOOL_CALLS_PER_TURN", "AGENT_MAX_HISTORY_MESSAGES", "AGENT_TIMEOUT_SECONDS", "SLA_CRITICAL_MINUTES", "ALERT_SMTP_HOST", "ALERT_SMTP_PORT", "ALERT_SMTP_USERNAME", "ALERT_SMTP_PASSWORD", "ALERT_EMAIL_FROM", "ALERT_SMTP_TIMEOUT", "DEFAULT_WORKER_PHONE", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID", "TWILIO_FROM_PHONE", "ALERT_SMS_TIMEOUT"):
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
except Exception:
    pass

import pages_account, pages_home, pages_report, pages_staff, pages_track, pages_help, pages_campus, pages_worker, pages_emergency
from auth_service import ensure_bootstrap_staff, ensure_demo_accounts, user_from_session
from config import get_settings
from database import init_db
from dialogs import render_modal
from logging_config import setup as setup_logging
from shared import PAGES
from ui import confetti, h, inject, md

st.set_page_config(page_title="ResolveAI: From complaint to resolution", page_icon="🧭", layout="wide")
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = st.query_params.get("theme") == "dark"

def _persist_theme():
    st.query_params["theme"] = "dark" if st.session_state.get("dark_mode") else "light"

settings = get_settings()
setup_logging(settings.log_level)
init_db()
ensure_bootstrap_staff()
ensure_demo_accounts()
st.session_state.setdefault("page", PAGES[0])
if st.session_state.get("goto_page") in PAGES:  # navigation requested from inside a dialog
    st.session_state["page"] = st.session_state.pop("goto_page")

# Stay signed in after a page refresh: the URL carries an unguessable session token (8 hours, revoked on sign-out)
_tok = st.query_params.get("s")
if _tok and "user" not in st.session_state:
    _u = user_from_session(_tok)
    if _u:
        st.session_state["user"] = _u.model_dump()
    else:
        del st.query_params["s"]

with st.container(key="nav"):
    brand, theme_control = st.columns([5, 1], vertical_alignment="center")
    _active_user = st.session_state.get("user") or {}
    _portal_context = (
        '<span class="portal-chip staff-chip">STAFF ADMIN · OPERATIONS</span>' if _active_user.get("role") == "staff"
        else '<span class="portal-chip worker-chip">WORKER · ' + h(str(_active_user.get("department") or "TASKS").upper()) + '</span>' if _active_user.get("role") == "worker"
        else '<span class="portal-chip student-chip">STUDENT · SERVICE DESK</span>' if _active_user.get("role") == "student"
        else '<span class="portal-chip guest-chip">CAMPUS SERVICE DESK</span>'
    )
    brand.markdown(
        '<div class="nav-brand"><div class="logo">Resolve<i>AI</i></div>'
        f'<span class="nav-context">{_portal_context}</span></div>', unsafe_allow_html=True,
    )
    theme_control.toggle("Dark mode", key="dark_mode", help="Switch between light and dark appearance", on_change=_persist_theme)
    with st.container(key="navradio"):
        _role = _active_user.get("role")
        _nav_pages = ({"student": ["Home", "Emergency", "Report an issue", "Track a ticket", "Account", "Help"],
                       "worker": ["Home", "Emergency", "Worker workspace", "Account", "Help"],
                       "staff": ["Home", "Emergency", "Staff workspace", "Campus Intelligence", "Account", "Help"]}.get(
                           _role, [PAGES[0], PAGES[8], *PAGES[1:8]]))
        if st.session_state.get("page") not in _nav_pages:
            st.session_state["page"] = {"student": "Home", "worker": "Worker workspace", "staff": "Staff workspace"}.get(_role, "Home")
        st.radio("Navigate", _nav_pages, horizontal=True, key="page", label_visibility="collapsed")
inject()

_render_page = {"Home": pages_home.render, "Report an issue": pages_report.render, "Track a ticket": pages_track.render, "Staff workspace": pages_staff.render,
               "Campus Intelligence": pages_campus.render, "Account": pages_account.render, "Help": pages_help.render,
               "Worker workspace": pages_worker.render, "Emergency": pages_emergency.render}[st.session_state["page"]]
if st.session_state["page"] in ("Report an issue", "Track a ticket"):
    with st.container(key="student_portal"):
        _render_page()
elif st.session_state["page"] == "Staff workspace":
    with st.container(key="staff_portal"):
        _render_page()
elif st.session_state["page"] == "Worker workspace":
    with st.container(key="worker_portal"):
        _render_page()
elif st.session_state["page"] == "Home":
    with st.container(key="landing_page"):
        _render_page()
else:
    _render_page()

if st.session_state.get("toast"):
    st.toast(st.session_state.pop("toast"), icon="✅")
render_modal()
if st.session_state.pop("confetti", False):
    md(confetti())
