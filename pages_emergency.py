"""Student-accessible, tap-to-call emergency contacts for AKGEC / Uttar Pradesh."""
import streamlit as st

from ui import h, md, page_head


CONTACTS = [
    ("112", "All emergencies · India", "Police, fire and medical response through the national emergency response system.", True),
    ("100", "Police · Uttar Pradesh", "Legacy direct police emergency number published by the Government of Uttar Pradesh.", False),
    ("101", "Fire and rescue", "Fire brigade and rescue; 112 is also the integrated emergency number.", False),
    ("108", "Ambulance · Uttar Pradesh", "Emergency ambulance service in Uttar Pradesh.", False),
    ("102", "Ambulance · Uttar Pradesh", "Ambulance number listed by the Government of Uttar Pradesh.", False),
    ("1090", "Women’s helpline · Uttar Pradesh", "Uttar Pradesh women’s helpline. For immediate danger, dial 112.", False),
]


def render() -> None:
    md('''<style>
.emergency-now{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:10px 0 20px;padding:22px 24px;border:1px solid #9D2A23;border-radius:16px;background:linear-gradient(110deg,#7F1D1D,#B42318);color:#fff;box-shadow:0 18px 38px -25px rgba(127,29,29,.65)}
.emergency-now .eyebrow{color:#FFE0D9}.emergency-now h2{margin:5px 0;font-size:clamp(22px,3vw,30px);color:#fff}.emergency-now p{margin:0;max-width:60ch;color:#FFF1ED}.emergency-now>a,.emergency-card>a,.emergency-campus>a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 16px;border-radius:10px;background:#fff;color:#7F1D1D;font-weight:700;text-decoration:none;white-space:nowrap}.emergency-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0 20px}.emergency-card{padding:18px;border:1px solid var(--line);border-radius:14px;background:var(--card);color:var(--ink)}.emergency-number{font:500 30px/1 var(--serif);letter-spacing:-.03em;color:#B42318}.emergency-card h3{margin:10px 0 4px;font-size:16px;color:var(--ink)}.emergency-card p{min-height:42px;margin:0 0 14px;color:var(--mute);font-size:13px;line-height:1.5}.emergency-card>a{background:#B42318;color:white}.emergency-campus{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px;border:1px solid var(--line);border-radius:14px;background:var(--sunk);color:var(--ink)}.emergency-campus .eyebrow{margin-bottom:4px}.emergency-campus p{margin:4px 0 0;color:var(--mute);font-size:13px}
@media(max-width:640px){.emergency-now{align-items:flex-start;flex-direction:column;padding:18px}.emergency-grid{grid-template-columns:1fr;gap:9px}.emergency-card p{min-height:0}.emergency-campus{align-items:flex-start;flex-direction:column}}
</style>''')
    page_head("Emergency contacts", "Get help now.", "Tap a number on your phone to call. If someone is in immediate danger, call 112 first; do not wait for a ticket or app response.")
    md('<section class="emergency-now"><div><div class="eyebrow">IMMEDIATE DANGER</div><h2>Call India’s emergency number</h2><p>112 connects emergency response. Tell the operator your location, what happened, and whether anyone is hurt.</p></div>'
       '<a href="tel:112" aria-label="Call emergency services at 112">Call 112 now</a></section>')
    md('<div class="emergency-grid">' + "".join(
        f'<article class="emergency-card{" emergency-primary" if primary else ""}"><div class="emergency-number">{h(number)}</div>'
        f'<h3>{h(title)}</h3><p>{h(details)}</p><a href="tel:{h(number)}" aria-label="Call {h(title)} at {h(number)}">Call {h(number)} ↗</a></article>'
        for number, title, details, primary in CONTACTS[1:]
    ) + "</div>")
    md('<section class="emergency-campus"><div><div class="eyebrow">CAMPUS CONTACT</div><b>AKGEC college contact</b><p>8744052891 · General college contact listed on AKGEC’s website. This is not identified as a 24-hour emergency line.</p></div>'
       '<a href="tel:8744052891" aria-label="Call AKGEC college contact at 8744052891">Call college</a></section>')
    st.caption("Emergency numbers and coverage can change. Use 112 for urgent help and follow the operator’s instructions. ResolveAI does not contact emergency services or share your location automatically.")
    st.markdown("Official sources: [India ERSS 112](https://112.gov.in/), [Uttar Pradesh emergency numbers](https://www.nri.up.gov.in/en/page/state-profile), [AKGEC contact](https://www.akgec.ac.in/admission-through-uptac-counselling/).")

