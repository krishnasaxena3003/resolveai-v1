import streamlit as st
from schemas import LIVE_STATUSES, Status, User
from shared import PAGES, auth_card, go
from ticket_service import list_tickets, staff_list_tickets, worker_list_tasks
from ui import h, md, tag


def _welcome(user):
    md(f'{tag(user["role"].title(), "g")}<div class="d3" style="margin-top:8px">Welcome back, {h(user["name"].split()[0])}.</div>')
    if user["role"] == "student":
        mine = list_tickets(reporter_id=user["id"])
        live, wait, done = sum(t.status in LIVE_STATUSES for t in mine), sum(t.status == Status.PENDING for t in mine), sum(t.status == Status.RESOLVED for t in mine)
        md(f'<div class="wel"><div><b>{live}</b><span>Being worked on</span></div><div><b style="color:#7A5AF8">{wait}</b><span>Need your sign-off</span></div><div><b style="color:#2E9E5B">{done}</b><span>Resolved</span></div></div>')
        if wait:
            md(f'<div class="callout wait"><b>{wait} fix{"es are" if wait != 1 else " is"} waiting for you.</b> Please confirm it is fixed, or tell the team it is not.</div>')
        st.button("Report an issue →", type="primary", key="wel_report", on_click=go, args=(PAGES[1],))
        st.button("Track my reports", key="wel_track", on_click=go, args=(PAGES[2],))
        st.button("Emergency help · call 112", key="wel_emergency", on_click=go, args=(PAGES[8],), type="secondary")
    elif user["role"] == "worker":
        tasks = worker_list_tasks(actor=User(**user))
        assigned = sum(t.assignee_id == user["id"] for t in tasks)
        available = sum(t.assignee_id is None for t in tasks)
        urgent = sum(t.critical_alert for t in tasks)
        md(f'<div class="wel"><div><b>{assigned}</b><span>Assigned to you</span></div><div><b style="color:#D98E04">{available}</b><span>Available in your team</span></div><div><b style="color:#E4572E">{urgent}</b><span>Safety alerts</span></div></div>')
        st.button("Open my worker tasks →", type="primary", key="wel_worker", on_click=go, args=(PAGES[7],))
    else:
        ts = staff_list_tickets(actor=User(**user))
        md(f'<div class="wel"><div><b>{sum(t.status in LIVE_STATUSES for t in ts)}</b><span>Active tickets</span></div><div><b style="color:#7A5AF8">{sum(t.status == Status.PENDING for t in ts)}</b><span>Awaiting students</span></div>'
           f'<div><b style="color:#E4572E">{sum(t.status == Status.REOPENED for t in ts)}</b><span>Reopened</span></div></div>')
        st.button("Open staff workspace →", type="primary", key="wel_staff", on_click=go, args=(PAGES[3],))


def render():
    user = st.session_state.get("user")
    left, right = st.columns([1.15, .85], gap="large")
    with left:
        md('<section class="campus-hero"><div class="hero-network" aria-hidden="true">' + ''.join(f'<i class="live-dot live-dot-{i}"></i>' for i in range(1, 9)) + '</div><div class="campus-hero-copy"><div class="eyebrow">AI-assisted campus support</div>'
           '<div class="d1" role="heading" aria-level="1">From complaint to resolution, <em>autonomously.</em></div>'
           '<p class="hero-p">Describe a problem by typing or speaking. ResolveAI routes it to the right team, checks for similar reports, and keeps you informed until you confirm it is fixed.</p>'
           '<div class="hero-tags">' + tag("Voice or text", "b") + tag("Photo evidence", "am") + tag("Human sign-off", "gn") + '</div></div></section>')
    with right:
        with st.container(key="panel_auth"):
            if user:
                _welcome(user)
            else:
                auth_card()
    md('''<div class="sec landing-sheet"><div class="eyebrow">Why ResolveAI?</div><div class="d2" role="heading" aria-level="2" style="margin-top:14px">Built to be clear about who did what.</div>
<div class="why">
<div><div class="n">(1).</div><div class="d3">Simple to report</div><p>A short description, an optional photo and a location. No technical knowledge needed.</p></div>
<div><div class="n">(2).</div><div class="d3">Structured, then checked</div><p>An LLM recommends fields. Application code validates every one before use.</p></div>
<div><div class="n">(3).</div><div class="d3">Fixed means you agree</div><p>Staff mark a fix with a note. The ticket closes only when you confirm it, or reopens if it is not fixed.</p></div>
<div><div class="n">(4).</div><div class="d3">One view for staff</div><p>Queues, deadlines, notes and evidence in a single workspace.</p></div></div></div>''')
    md('<div class="sec landing-sheet phil"><div class="eyebrow">Our principle</div><div class="big">The AI <em>recommends.</em> Code validates and acts. People decide what is resolved.</div></div>')
    rows = [("1. Analyze", "AI recommends", "o", "Complaint text becomes summary, category, priority, department.", "Complaint is treated as untrusted input."),
            ("2. Validate", "Code", "g", "Output checked against allowed values.", "Unknown values go to Other or staff review."),
            ("3. Find duplicates", "Code", "g", "Text similarity against open tickets.", "Matches are candidates, not proof."),
            ("4. Create", "Code + you", "b", "Ticket saved with a generated ID. Photos are cleaned and stored privately.", "Errors are reported, never hidden."),
            ("5. Verify", "Code", "g", "Record read back after saving.", "Success shown only after confirmation."),
            ("6. Fix", "Staff", "v", "Staff mark the issue fixed and describe what was done.", "A fix needs a written note."),
            ("7. Sign-off", "You", "b", "You confirm it is fixed, or reopen it with a reason.", "Staff cannot close it for you, except after a long silence.")]
    body = "".join(f'<tr><td>{a}</td><td>{tag(b, k)}</td><td class="hm">{c}</td><td class="hm">{d}</td></tr>' for a, b, k, c, d in rows)
    md('<div class="sec landing-sheet"><div class="eyebrow">Method, not magic</div><div class="d2" role="heading" aria-level="2" style="margin-top:14px">Seven stages. Every one accountable.</div>'
       f'<table class="wf"><thead><tr><th>Stage</th><th>Owner</th><th class="hm">What happens</th><th class="hm">Guardrail</th></tr></thead><tbody>{body}</tbody></table></div>')
    with st.container(key="cta"):
        st.button("Begin a report →", type="primary", key="cta_btn", on_click=go, args=(PAGES[1],))
