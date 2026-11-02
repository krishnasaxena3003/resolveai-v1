# Demo script (about 4 minutes)

Before presenting: set `DEMO_MODE=1` in a private local `.env`, restart the app, and (optionally) run `python seed.py --demo-accounts`. The Home sign-in panel provides one-touch demo access and shows the selected fictional email/password; all demo accounts use `DemoPass123` for local demos only. Worker accounts are available by occupation. Never enable demo mode on a public deployment. Set `LLM_API_KEY`, run `python check_ai.py` and confirm `Mode: llm`. Have a backup plan: if Wi-Fi fails, the app still works on fallback rules and says so on screen.

1. **How it works (30 s).** Open the first tab. Say: the AI recommends, code validates and acts, staff decide.
2. **Sign in (20 s).** Use the Home panel’s one-touch demo access. Show the student, staff and occupation-specific worker portals; the worker gets a team-only task board. Worker accounts are provisioned by admins, not publicly self-created. Open Emergency briefly to show tap-to-call numbers.
3. **Report an issue (60 s).** Choose one of the ten report examples and click "Use selected sample", then "Run AI check". Point out: recommended category, priority, service team, the "AI-assisted" or "Fallback rules" label, and the staff review flag where applicable.
4. **Duplicate check (45 s).** The seeded ticket appears as a possible duplicate with evidence. Choose "Same issue: save my report and link it". Stress: the report is kept, nothing is deleted.
5. **Verified save (20 s).** Show the ticket ID and the one-time tracking code. Say: this appeared only after the app read the saved record back.
6. **Track a ticket (30 s).** Show 'Your reports' (no code needed while signed in). Then try the ID and a wrong code to show it is refused.
7. **Staff workspace (90 s).** On an empty demo database, generate ten clearly labelled sample tickets. Then walk the queue rail (Active, My queue, Unassigned, Needs review, Overdue), point at priority colours and SLA timers, assign a ticket to yourself, add one internal and one student-visible note, link the suggested duplicate, then resolve. Use Campus Intelligence to explore verified library and named lab locations; switch on the sample-ticket filter for demo records. Go back to Track and show the student sees the update.
8. **Campus Intelligence agent (60 s).** In Campus Intelligence, enter a real ticket reference from the queue and ask “What related unresolved reports exist at this location?” Show the response's findings, ticket references, recommendations, and any uncertainty. Follow up with “What does the timeline show?” to demonstrate session context. Clear the investigation, then explain that the agent has read-only tools and cannot perform the suggested work. Real model investigation requires a configured provider key; mock tests do not establish real-model quality.
9. **Failure handling (30 s).** Temporarily remove the API key (or use a wrong one), submit another report: the app labels "Fallback rules", still creates a verified ticket, and flags it for review. In the agent, the UI reports that investigation AI is unavailable and directs staff to review the records directly.

Optional extras (30 s each): on the Staff workspace open "Activity" on a ticket to show the audit trail; use "Help a student reset their password" then the student's Forgot password tab; refresh the page to show you stay signed in.

Likely judge questions
- *Is the AI accuracy proven?* We report an evaluation on a small hand-labelled set in `evaluation/RESULTS.md`, including weaknesses. We make no accuracy claim beyond that.
- *Prompt injection?* Complaint text is wrapped as data, output is validated, and routing is decided by code.
- *Why not delete duplicates?* A false match must never lose a real complaint.
