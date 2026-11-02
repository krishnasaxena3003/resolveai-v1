"""State, callbacks and widgets shared by every page."""
import streamlit as st
from auth_service import (DEMO_ACCOUNTS, DEMO_PASSWORD, DEMO_WORKER_ACCOUNTS, AuthError, authenticate, create_session, end_session, redeem_reset, register_student, user_from_session)
from attachments import AttachmentError, list_attachments, read_attachment
from config import get_settings
from schemas import User
from ui import h, md, page_head

PAGES = ["Home", "Report an issue", "Track a ticket", "Staff workspace", "Campus Intelligence", "Account", "Help", "Worker workspace", "Emergency"]


def go(page):
    st.session_state["page"] = page


def go_later(page):
    """For buttons inside dialogs, which run after the navigation widget exists: apply the page change at the start of the next run."""
    st.session_state["goto_page"] = page


# ---------------------------------------------------------------- auth callbacks (run before the page redraws)
def _sign_in(user, after=None):
    st.session_state["user"] = user.model_dump()
    st.session_state.pop("auth_err", None)
    st.query_params["s"] = create_session(user.id)
    st.session_state["page"] = after or (PAGES[3] if user.role == "staff" else PAGES[7] if user.role == "worker" else PAGES[1])
    st.session_state["toast"] = f"Signed in as {user.name}"


def do_login():
    g = st.session_state.get
    role = {"Staff": "staff", "Worker": "worker"}.get(g("si_role"), "student")
    try:
        _sign_in(authenticate(g("si_email", ""), g("si_pw", ""), role=role,
                              occupation=g("si_occupation") if role == "worker" else None))
    except AuthError as e:
        st.session_state["auth_err"] = ("si", str(e))


def do_demo(email):
    try:
        _sign_in(authenticate(email, DEMO_PASSWORD))
    except AuthError as e:
        st.session_state["auth_err"] = ("si", str(e))


def do_register():
    g = st.session_state.get
    if g("rg_pw", "") != g("rg_pw2", ""):
        st.session_state["auth_err"] = ("rg", "The two passwords do not match."); return
    try:
        _sign_in(register_student(g("rg_name", ""), g("rg_email", ""), g("rg_pw", "")), PAGES[1])
    except AuthError as e:
        st.session_state["auth_err"] = ("rg", str(e))


def do_reset():
    g = st.session_state.get
    try:
        redeem_reset(g("rs_email", ""), g("rs_code", ""), g("rs_pw", ""))
        st.session_state.pop("auth_err", None)
        st.session_state["auth_ok"] = ("rs", "Password updated. You can now sign in with your new password.")
    except AuthError as e:
        st.session_state["auth_err"] = ("rs", str(e))
        st.session_state.pop("auth_ok", None)


def do_logout():
    end_session(st.query_params.get("s"))
    if "s" in st.query_params:
        del st.query_params["s"]
    for k in ("user", "prepared", "prepared_files", "created", "created_photos", "critical_delivery", "critical_sms_delivery", "voice_audio", "voice_upload", "voice_transcript", "clear_voice_audio_on_rerun",
              "desc", "photos", "loc_sel", "loc_other", "auth_err", "modal", "sel", "worker_ticket", "worker_comment"):
        st.session_state.pop(k, None)
    for k in list(st.session_state):
        if k.startswith("campus_agent_"):
            st.session_state.pop(k, None)
    st.session_state["page"] = PAGES[0]


def auth_error(form):
    e = st.session_state.get("auth_err")
    if e and e[0] == form:
        st.error(e[1])


def auth_card(title="Welcome to ResolveAI", sub="Sign in to report problems and follow them to resolution."):
    """The portal: sign in (student or staff), create a student account, or recover a password. Used on Home and Account."""
    md(f'<div class="d3">{h(title)}</div><p class="authsub">{h(sub)}</p>')
    t_in, t_new, t_rs = st.tabs(["Sign in", "Create account", "Forgot password"])
    with t_in:
        st.radio("I am a", ["Student", "Staff", "Worker"], horizontal=True, key="si_role")
        with st.form("signin_form"):
            st.text_input("Email", key="si_email", placeholder="name@college.edu")
            st.text_input("Password", type="password", key="si_pw")
            if st.session_state.get("si_role") == "Worker":
                from schemas import DEPARTMENTS
                st.selectbox("Your occupation / response team", DEPARTMENTS, key="si_occupation")
            st.form_submit_button("Sign in →", type="primary", key="si_submit", on_click=do_login)
        auth_error("si")
        if st.session_state.get("si_role") == "Staff":
            md('<p class="note">Staff accounts are created by your administrator. There is no public staff sign-up.</p>')
        elif st.session_state.get("si_role") == "Worker":
            md('<p class="note">Worker accounts and occupations are assigned by a staff admin. Select the same occupation that was assigned to your account.</p>')
    with t_new:
        with st.form("register_form"):
            st.text_input("Full name", key="rg_name", max_chars=80)
            st.text_input("Email", key="rg_email", max_chars=120)
            st.text_input("Password (at least 8 characters)", type="password", key="rg_pw")
            st.text_input("Repeat password", type="password", key="rg_pw2")
            st.form_submit_button("Create student account →", type="primary", key="rg_submit", on_click=do_register)
        auth_error("rg")
    with t_rs:
        st.caption("Ask a member of staff for a one-time reset code, then choose a new password here.")
        with st.form("reset_form"):
            st.text_input("Email", key="rs_email")
            st.text_input("Reset code", key="rs_code", placeholder="ABCD-1234")
            st.text_input("New password (at least 8 characters)", type="password", key="rs_pw")
            st.form_submit_button("Reset password →", type="primary", key="rs_submit", on_click=do_reset)
        auth_error("rs")
        ok = st.session_state.get("auth_ok")
        if ok and ok[0] == "rs":
            st.success(ok[1])
    if get_settings().demo_mode:
        md('<div class="demo-h">One-touch demo access</div>')
        role = st.radio("Demo portal", ["Student", "Staff", "Worker"], horizontal=True, key="demo_role")
        if role == "Student":
            choices = [(name, email, dept) for name, email, account_role, dept in DEMO_ACCOUNTS if account_role == "student"]
        elif role == "Staff":
            choices = [(name, email, dept or "All departments") for name, email, account_role, dept in DEMO_ACCOUNTS if account_role == "staff"]
        else:
            choices = [(name, email, dept) for name, email, dept in DEMO_WORKER_ACCOUNTS]
        labels = {f"{name} · {dept}": email for name, email, dept in choices}
        choice = st.selectbox("Choose a demo account", list(labels), key=f"demo_account_choice_{role.lower()}")
        email = labels[choice]
        st.code(f"Email: {email}\nPassword: {DEMO_PASSWORD}", language=None)
        st.button("Enter this demo account →", key="demo_one_touch", on_click=do_demo, args=(email,), type="primary", use_container_width=True)
        st.caption("Demo accounts use fictional @demo.test emails and shared sample data. Enable DEMO_MODE=1 only in a private demo environment; never on a public production deployment.")


def require(role, eyebrow, why):
    """Show a sign-in prompt and stop unless the signed-in account has the right role."""
    u = st.session_state.get("user")
    token = st.query_params.get("s")
    if u and token and user_from_session(token) is None:
        st.session_state.pop("user", None)
        del st.query_params["s"]
        u = None
    if u and u["role"] == role:
        return u
    page_head(eyebrow, "Please sign in." if not u else f"This page is for {role} accounts.", why)
    with st.container(key="panel_gate"):
        st.write("You are signed in as a " + u["role"] + "." if u else f"Sign in with a {role} account to continue.")
        st.button("Go to sign in →", type="primary", key="gate_btn", on_click=go, args=(PAGES[5],))
    st.stop()


def current_user():
    u = st.session_state.get("user")
    return User(**u) if u else None


def show_photos(ticket_id, viewer, kinds=("report", "resolution"), width=150):
    """Photos for one ticket. Access is checked for every file; nothing is served from a public path."""
    items = [a for a in list_attachments(ticket_id) if a["kind"] in kinds]
    if not items:
        return False
    cols = st.columns(min(3, len(items)))
    for i, a in enumerate(items):
        try:
            cols[i % len(cols)].image(read_attachment(a["id"], viewer=viewer), caption=("Fix evidence" if a["kind"] == "resolution" else "Photo") + f" · {a['original_name']}", width=width)
        except AttachmentError as e:
            cols[i % len(cols)].caption(str(e))
    return True


def style_fig(fig, color=None):
    dark = bool(st.session_state.get("dark_mode", False))
    text_color, muted_color = ("#F0F4EF", "#B2C0B6") if dark else ("#1E1A17", "#6F675F")
    fig.update_layout(height=290, margin=dict(l=8, r=8, t=10, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="DM Sans, sans-serif", color=text_color), bargap=.45, showlegend=False)
    fig.update_xaxes(showgrid=False, title=None, automargin=True, tickfont=dict(color=muted_color), zerolinecolor="#35443A" if dark else "#E6DFD4")
    fig.update_yaxes(showgrid=False, title=None, automargin=True, tickfont=dict(color=muted_color), zerolinecolor="#35443A" if dark else "#E6DFD4")
    if fig.data and fig.data[0].orientation == "h":
        fig.update_xaxes(dtick=1)
    else:
        fig.update_yaxes(dtick=1)
    if color:
        fig.update_traces(line_color=color, fillcolor="rgba(47,111,237,.18)") if fig.data and fig.data[0].type == "scatter" else fig.update_traces(marker_color=color)
    return fig
