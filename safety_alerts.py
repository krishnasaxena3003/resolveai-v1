"""Conservative life-safety hazard detection and staff email alerts."""
from email.message import EmailMessage
import base64
import logging
import re
import smtplib
import sqlite3
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import get_settings
from database import connect
from schemas import SAFETY_DEPARTMENT, TicketRecord

log = logging.getLogger("resolveai.safety")
_HAZARD = re.compile(
    r"\b(?:fire|smoke|gas leak|gas smell|gas odou?r|explosion|live wire|exposed wire|"
    r"electrical arc|electric shock|electrocution|sparks?|sparking|short circuit|burning smell|high voltage|"
    r"building collapse|ceiling collapse|structural collapse|someone trapped|person trapped|"
    r"carbon monoxide|chemical spill|medical emergency|unconscious|severe bleeding|serious injury)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no|not|never|without)\b(?:\W+\w+){0,2}\W*$", re.IGNORECASE)


def is_critical_hazard(text: str | None) -> bool:
    """Flag explicit safety hazards; staff still verify every flag before acting."""
    text = " ".join((text or "").split())
    for match in _HAZARD.finditer(text):
        prefix = text[max(0, match.start() - 28):match.start()]
        if _NEGATION.search(prefix):
            continue
        context = text[max(0, match.start() - 18):match.end() + 22].lower()
        if "false alarm" in context or "fire drill" in context or "fire safety poster" in context:
            continue
        return True
    return False


def email_staff_critical_alert(ticket: TicketRecord) -> tuple[int, int, bool]:
    """Send a minimal, privacy-conscious email to safety responders and all-department admins.

    Returns sent count, recipient count, and whether SMTP is configured. Delivery failures never
    undo a saved ticket; the live safety queue remains the in-app fallback.
    """
    if not ticket.critical_alert:
        return 0, 0, False
    settings = get_settings()
    configured = bool(settings.alert_smtp_host and settings.alert_email_from)
    if not configured:
        return 0, 0, False
    try:
        with connect() as conn:
            recipients = [r[0] for r in conn.execute(
                "SELECT email FROM users WHERE is_active=1 AND is_demo=0 AND ((role='worker' AND department=?) OR (role='staff' AND (department=? OR department IS NULL))) ORDER BY id",
                (SAFETY_DEPARTMENT, SAFETY_DEPARTMENT),
            )]
    except sqlite3.Error:
        log.warning("critical_alert_recipient_lookup_failed", extra={"ticket_id": ticket.ticket_id})
        return 0, 0, True
    if not recipients:
        return 0, 0, True

    message = EmailMessage()
    message["Subject"] = f"[ResolveAI SAFETY ALERT] {ticket.ticket_id}"
    message["From"] = settings.alert_email_from
    message.set_content(
        "A report has been flagged for a potential life-safety hazard.\n\n"
        f"Ticket: {ticket.ticket_id}\n"
        f"Responder team: {SAFETY_DEPARTMENT}\n"
        f"Location: {ticket.location or 'Not provided'}\n"
        f"Target response time: {settings.sla_critical_minutes:g} minutes\n\n"
        "Sign in to ResolveAI and open the Critical safety queue. Verify the report and follow campus emergency procedures.\n"
        "Do not use this ticket system as a replacement for contacting emergency services in immediate danger.\n"
    )
    sent = 0
    try:
        context = ssl.create_default_context()
        if settings.alert_smtp_port == 465:
            server_context = smtplib.SMTP_SSL(settings.alert_smtp_host, settings.alert_smtp_port,
                                               timeout=settings.alert_smtp_timeout, context=context)
        else:
            server_context = smtplib.SMTP(settings.alert_smtp_host, settings.alert_smtp_port,
                                           timeout=settings.alert_smtp_timeout)
        with server_context as server:
            if settings.alert_smtp_port != 465:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
            if settings.alert_smtp_username:
                server.login(settings.alert_smtp_username, settings.alert_smtp_password or "")
            for recipient in recipients:
                try:
                    server.send_message(message, to_addrs=[recipient])
                    sent += 1
                except (OSError, smtplib.SMTPException):
                    log.warning("critical_alert_delivery_failed", extra={"ticket_id": ticket.ticket_id})
    except (OSError, smtplib.SMTPException, ValueError):
        log.warning("critical_alert_service_unavailable", extra={"ticket_id": ticket.ticket_id})
    return sent, len(recipients), True


def sms_safety_workers_critical_alert(ticket: TicketRecord) -> tuple[int, int, bool]:
    """Send a minimal SMS to real safety responders; never blocks or rolls back ticket creation."""
    if not ticket.critical_alert:
        return 0, 0, False
    settings = get_settings()
    sender = settings.twilio_messaging_service_sid or settings.twilio_from_phone
    configured = bool(settings.twilio_account_sid and settings.twilio_auth_token and sender)
    if not configured:
        return 0, 0, False
    try:
        with connect() as conn:
            recipients = list(dict.fromkeys(r[0] for r in conn.execute(
                "SELECT phone FROM users WHERE role='worker' AND is_active=1 AND is_demo=0 AND department=? AND phone IS NOT NULL AND trim(phone)!='' ORDER BY id",
                (SAFETY_DEPARTMENT,),
            )))
    except sqlite3.Error:
        log.warning("critical_sms_recipient_lookup_failed", extra={"ticket_id": ticket.ticket_id})
        return 0, 0, True
    if not recipients:
        return 0, 0, True

    body = (f"ResolveAI SAFETY ALERT: {ticket.ticket_id}. Potential hazard reported at "
            f"{ticket.location or 'campus location not provided'}. Check the Critical safety queue now "
            "and follow campus emergency procedures. For immediate danger, contact emergency services.")[:500]
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    authorization = base64.b64encode(f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()).decode()
    sent = 0
    for phone in recipients:
        fields = {"To": phone, "Body": body}
        if settings.twilio_messaging_service_sid:
            fields["MessagingServiceSid"] = settings.twilio_messaging_service_sid
        else:
            fields["From"] = settings.twilio_from_phone
        request = Request(endpoint, data=urlencode(fields).encode(), headers={
            "Authorization": f"Basic {authorization}", "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=settings.alert_sms_timeout) as response:
                if 200 <= response.status < 300:
                    sent += 1
        except Exception:
            # Delivery errors must never undo a saved report. Do not log provider responses,
            # message bodies, credentials, or phone numbers.
            log.warning("critical_sms_delivery_failed", extra={"ticket_id": ticket.ticket_id})
    return sent, len(recipients), True
