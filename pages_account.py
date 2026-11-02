import streamlit as st
from shared import PAGES, auth_card, do_logout, go
from ui import h, md, page_head, tag
from auth_service import worker_phone
from schemas import User


def render():
    me = st.session_state.get("user")
    if me:
        page_head("Account", f"Hello, {me['name'].split()[0]}.")
        with st.container(key="panel_me"):
            md(f'{tag(me["role"].title(), "g")}<dl class="out" style="margin-top:8px"><dt>Name</dt><dd>{h(me["name"])}</dd><dt>Email</dt><dd>{h(me["email"])}</dd>'
               + (f'<dt>{"Occupation / team" if me["role"] == "worker" else "Department"}</dt><dd>{h(me.get("department") or "All departments")}</dd>' if me["role"] in ("staff", "worker") else "")
               + (f'<dt>SMS contact</dt><dd>{h(worker_phone(User(**me)) or "Not set")}</dd>' if me["role"] == "worker" else "") + "</dl>")
            if me["role"] == "student":
                st.button("Report an issue →", type="primary", key="acct_report", on_click=go, args=(PAGES[1],))
                st.button("My reports", key="acct_track", on_click=go, args=(PAGES[2],))
            elif me["role"] == "worker":
                st.button("Open my worker workspace →", type="primary", key="acct_worker", on_click=go, args=(PAGES[7],))
            else:
                st.button("Open staff workspace →", type="primary", key="acct_staff", on_click=go, args=(PAGES[3],))
            st.button("Sign out", key="logout", on_click=do_logout)
        md('<p class="note" style="margin-top:18px">Signed-in sessions last 8 hours. Do not share the page address while signed in.</p>')
    else:
        page_head("Account", "Welcome.", "Students sign in to report issues, staff admins manage tickets, and workers use an occupation-specific task board.")
        with st.container(key="panel_auth"):
            auth_card()
