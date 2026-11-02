"""A small, deterministic help chat with answers grounded in ResolveAI's shipped features."""
import re

import streamlit as st

from ui import md, page_head

FAQ = [
    ("How do I report an issue?", "Sign in as a student, open **Report an issue**, describe what happened, choose a location and attach at least one photo. Review the suggested category and priority before submitting. You can also record your complaint in English, Hindi, or another listed language and review the transcript first."),
    ("How do I track my ticket?", "Open **Track a ticket** while signed in to see your reports and updates. You can also look up a single ticket with its ticket ID and tracking code."),
    ("The team says it is fixed. What should I do?", "Open **Track a ticket**, rate the campus team's repair from 1 to 5 stars, and choose **Submit rating & confirm fix** to close it. If the issue is not fixed, reopen it with a note instead."),
    ("How does voice mode work?", "Report, staff and worker workspaces support voice dictation. Choose a spoken language or Auto-detect, record a short WAV clip, then transcribe it. Review and edit the words before saving. Audio is sent to the configured speech service only when you request transcription and is not saved as a ticket attachment."),
    ("Where is my data stored?", "This project uses SQLite, a relational database in one local file (configured with DB_PATH). Uploaded photos are stored separately in the private UPLOAD_DIR. See the Database section in README.md for tables, backups and deployment limits."),
    ("How can staff update a ticket?", "Staff sign in, open **Staff workspace**, select a queue and ticket, then update its assignment, status, category, priority or department. Staff can add a public update or an internal note in the ticket timeline."),
    ("How do worker accounts and tasks work?", "A staff admin creates your worker account and assigns an occupation. At **Account**, choose **Worker** and select the same occupation to sign in. **Worker workspace** shows tasks assigned to you plus unassigned tasks for your team. Claim an available task before opening its evidence; then record progress, add student-visible updates, and attach one repair photo before marking work complete."),
    ("Why is a photo required?", "A photo helps staff route a student report and gives the student evidence to review when staff or a worker says a repair is complete. Reports need at least one issue photo; marking a repair complete needs a repair photo."),
    ("Why did the app use standard rules instead of AI?", "ResolveAI uses standard rules when its language-model service is unavailable or not configured. The staff workspace labels these tickets for review. Check that LLM_API_KEY and the provider settings are configured in the deployment secrets."),
    ("How do I sign in or reset my password?", "Open **Account**. Students can create an account or use a one-time reset code from staff. Staff and worker accounts are created by an administrator; workers must choose their assigned occupation at sign-in."),
    ("Can I delete or withdraw a ticket?", "You can withdraw your own report within five minutes if it is still open and unassigned. Choose a reason and confirm. The report, photos and history are retained for staff; withdrawing it does not restore your daily report allowance."),
    ("How do I contact emergency services?", "Open Emergency from the navigation. Tap 112 for immediate danger; it is India's integrated emergency response number. The page also lists police, fire, ambulance and Uttar Pradesh women’s helpline contacts. ResolveAI cannot call or share your location for you."),
]


def answer(question: str) -> str:
    """Return a fixed FAQ answer; unknown questions never trigger a model call."""
    q = re.sub(r"[^a-z0-9 ]", " ", (question or "").lower())
    q = " ".join(q.split())
    aliases = [
        (0, ("report", "submit", "complaint", "file an issue", "new issue")),
        (1, ("track", "status", "where is", "ticket id", "tracking code")),
        (2, ("fixed", "resolved", "reopen", "not fixed", "sign off", "sign-off")),
        (3, ("voice", "microphone", "record", "audio", "transcri")),
        (4, ("database", "sqlite", "stored", "storage", "data", "backup", "photo")),
        (5, ("staff", "assign", "assignment", "update ticket", "internal note", "department")),
        (6, ("worker", "occupation", "task board", "claim a task", "worker task")),
        (7, ("ai", "model", "rules", "fallback", "not configured")),
        (8, ("sign in", "login", "password", "reset", "account")),
        (9, ("withdraw", "delete ticket", "cancel report", "remove report")),
        (10, ("emergency", "ambulance", "police", "fire brigade", "fire service", "112", "urgent help")),
    ]
    for index, phrases in aliases:
        if any(phrase in q for phrase in phrases):
            return FAQ[index][1]
    return "I can help with student reports, worker tasks, staff updates, ticket tracking, voice reports, data storage, AI setup and account access. Try one of the suggested questions below."


def _ask(question: str) -> None:
    st.session_state.setdefault("help_messages", []).extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer(question)},
    ])


def render() -> None:
    page_head("Help", "Ask ResolveAI", "Quick answers about reports, tickets, voice input, accounts and how the app works.")
    st.caption("This helper uses a fixed set of project FAQs. It does not send your message to an AI service.")
    messages = st.session_state.setdefault("help_messages", [])
    with st.container(key="help_chat"):
        md('<div class="help-chat-heading"><span class="help-chat-mark">R</span><div><b>ResolveAI Help</b><small>Answers about using your campus support desk</small></div><span class="help-online"><i></i>Ready</span></div>')
        if not messages:
            md('<div class="help-welcome"><span>👋</span><div><b>Hi, how can I help?</b><p>Choose a common question or type what you need help with.</p></div></div>')
        for message in messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        prompt = st.chat_input("Ask about using ResolveAI")

    with st.container(key="help_questions"):
        st.markdown("**Common questions**")
        columns = st.columns(2)
        for i, (question, _) in enumerate(FAQ):
            columns[i % 2].button(question, key=f"faq_{i}", on_click=_ask, args=(question,), use_container_width=True)

    if prompt and prompt.strip():
        _ask(prompt.strip())
        st.rerun()

    if messages and st.button("Clear conversation", key="clear_help"):
        st.session_state["help_messages"] = []
        st.rerun()

