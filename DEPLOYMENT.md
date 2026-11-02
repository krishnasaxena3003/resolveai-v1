# Deployment guide (Streamlit Community Cloud)

1. Push the project to a GitHub repository. `.env`, `*.db` and `secrets.toml` are git-ignored. Confirm with `git status` that no key is staged.
2. At share.streamlit.io choose "New app", select the repo and `app.py`.
3. In Advanced settings > Secrets paste (TOML):
       LLM_API_KEY = "your-key"
       LLM_BASE_URL = "https://api.groq.com/openai/v1"
       LLM_MODEL = "llama-3.3-70b-versatile"
       STAFF_EMAIL = "you@college.edu"
       STAFF_PASSWORD = "a-long-unique-password"
       AGENT_MAX_TURNS = 4
       AGENT_MAX_TOOL_CALLS = 8
       AGENT_MAX_TOOL_CALLS_PER_TURN = 3
       AGENT_MAX_HISTORY_MESSAGES = 8
       AGENT_TIMEOUT_SECONDS = 30
       # Optional device alert delivery for critical safety reports:
       ALERT_SMTP_HOST = "smtp.example.edu"
       ALERT_SMTP_PORT = 587
       ALERT_SMTP_USERNAME = "resolveai-alerts@example.edu"
       ALERT_SMTP_PASSWORD = "use-an-app-password-or-relay-secret"
       ALERT_EMAIL_FROM = "resolveai-alerts@example.edu"
       # Optional Twilio SMS alerts to non-demo Campus Safety workers:
       DEFAULT_WORKER_PHONE = "+916398758826"
       TWILIO_ACCOUNT_SID = "AC..."
       TWILIO_AUTH_TOKEN = "..."
       TWILIO_MESSAGING_SERVICE_SID = "MG..." # or set TWILIO_FROM_PHONE instead
       # TWILIO_FROM_PHONE = "+1..."
4. Deploy and sign in at Account > Staff with that email and password. Create response workers in the Staff workspace or using `python create_user.py worker "Safety Responder" safety@college.edu --occupation "Campus Safety & Emergency Response"` (use other occupations such as `Electrical Maintenance` as needed). Staff accounts without a department are all-department admins and receive every critical safety alert. Then delete STAFF_EMAIL and STAFF_PASSWORD from Secrets.
5. Run the demo script once.

Worker contact numbers use international E.164 format. Staff admins can enter or update a contact under Staff workspace > System. Critical SMS goes only to real, non-demo workers in Campus Safety & Emergency Response; it contains a ticket reference and location, not reporter details. A Twilio account, approved sender, and provider configuration are required. Trial accounts can message only verified destination numbers. SMS delivery never replaces direct emergency contact.

For a private local walkthrough, set `DEMO_MODE=1` in `.env` and restart the app. The Home sign-in panel offers one-touch student, staff and occupation-specific worker access and displays the selected fictional email and shared password `DemoPass123`. Each worker occupation has its own login: `worker@demo.test` (Electrical Maintenance), `worker.it@demo.test` (IT/Network Support), `worker.plumbing@demo.test` (Plumbing), `worker.hostel@demo.test` (Hostel Maintenance), `worker.lab@demo.test` (Equipment/Lab Support), `worker.admin@demo.test` (General Administration), and `worker.safety@demo.test` (Campus Safety & Emergency Response). These published demo credentials are unsafe for public use; never enable demo mode on a public deployment.

## Things to know before real use
- **Storage:** SQLite lives on the app's disk. Community Cloud can reset it on restart or redeploy, so seed data right before demos. For real use switch to a managed database.
- **Accounts:** students self-register; staff accounts are admin-created only. Set `ALLOWED_EMAIL_DOMAINS` (e.g. `college.edu`) to limit sign-ups to your college. Passwords are salted scrypt hashes; accounts lock for 5 minutes after 5 failures.
- **No email service:** there is no email verification and no emailed reset link. Instead, staff issue a one-time reset code (valid 30 minutes) from the dashboard, and the admin can reset any password from the command line: `python create_user.py reset <email>`.
- **Sessions:** a sign-in lasts 8 hours and survives a page refresh. The session token travels in the page address (`?s=...`), is stored hashed on the server, and is revoked on sign-out or password reset. Anyone who copies the address while you are signed in can use your session, so do not share it or screenshot it.
- **Roles:** staff-only actions are checked against the database in the service layer, not only in the page. Every change to a ticket is recorded in an activity log (who, what, when) shown to staff.
- **Guest lookups:** wrong tracking codes are counted per ticket in the database; 5 failures lock that ticket's lookup for 10 minutes.
- **Backups:** staff can download all tickets as CSV (spreadsheet formulas are neutralised). Do this regularly because hosted storage can reset.
- **Privacy:** complaint text is sent to the LLM provider. Do not submit personal or sensitive information in demos. Decide retention rules before any real deployment.
- **Model names change.** If the API rejects the model, update `LLM_MODEL` from your provider console.


## Run with Docker (recommended over Streamlit Cloud for anything real)
    cp .env.example .env        # fill in LLM_API_KEY, STAFF_EMAIL, STAFF_PASSWORD, ALLOWED_EMAIL_DOMAINS
    docker compose up -d --build
The app listens on 127.0.0.1:8501 only. Put a TLS-terminating proxy in front. Caddy example (automatic HTTPS):

    resolve.yourcollege.edu {
        encode gzip
        header Strict-Transport-Security "max-age=31536000"
        header X-Content-Type-Options nosniff
        header Referrer-Policy no-referrer
        reverse_proxy 127.0.0.1:8501
    }
The `backup` service writes a consistent copy of the database to the data volume every 24 hours and keeps 14. Copy those off the machine. To restore: stop the app, copy a backup over `/data/resolveai.db`, start the app.

## What is production-grade now, and what is not
Covered and tested: salted password hashing, account lockout, server-side sessions, role checks in the service layer, audit log, per-student AI and report limits, SLA timers, schema versioning that upgrades older databases and refuses newer ones, structured JSON logs without complaint text or secrets, health check, online backups, pinned dependencies, CI with static checks, non-root container with a health check.

Still NOT production-grade (decide before real institutional use):
- **Single-node SQLite.** One writer, no high availability, no point-in-time recovery. For many concurrent users move to PostgreSQL.
- **No email verification, no MFA, no emailed reset links.**
- **Session token travels in the page address**, which can leak through screenshots, shared links and proxy logs.
- **No per-IP rate limiting or bot protection**; add at the proxy.
- **Privacy and legal:** complaint text goes to the LLM provider. You need a data-processing agreement, a retention and deletion policy, and a notice to students. Not automated here.
- **Accessibility** has not been audited against WCAG, and **load, penetration and failure testing** have not been done.
- **Monitoring and alerting:** logs are structured, but nothing ships them anywhere or pages anyone.
- **Real-model quality** is unmeasured until you run `python eval_ai.py` with your key.
- **Agent behavior** is tested with deterministic mocked responses in the regular test suite. A live investigation requires an API key and a provider/model with compatible tool calling; review provider behavior and privacy before deployment. Agent execution limits have hard application caps.
# Critical hazard notifications

The Critical safety queue refreshes every 30 seconds in an open staff workspace. To deliver alerts to staff devices by email, configure SMTP credentials as deployment secrets: `ALERT_SMTP_HOST`, `ALERT_SMTP_PORT` (587 for STARTTLS or 465 for TLS), `ALERT_SMTP_USERNAME`, `ALERT_SMTP_PASSWORD`, and `ALERT_EMAIL_FROM`. Keep these values out of source control. ResolveAI emails non-demo staff accounts assigned to **Campus Safety & Emergency Response** plus staff admins whose department is blank. Email contains the ticket reference, response team, location, and response target, but not the reporter's name or full complaint.

Create named response-team accounts with `python create_user.py staff "Responder Name" responder@college.edu --department "Campus Safety & Emergency Response"`. An account without a department acts as an all-department staff admin. Email alerts require a verified SMTP relay; without it, tickets still enter the live in-app safety queue. Notification delivery does not replace direct emergency contact.
