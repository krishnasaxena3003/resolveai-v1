"""Settings come from environment variables only. Keys are never hardcoded."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    model: str
    db_path: str
    dup_threshold: float
    ai_timeout: float
    speech_api_key: str | None = None
    speech_base_url: str = "https://api.groq.com/openai/v1"
    speech_model: str = "whisper-large-v3-turbo"
    speech_timeout: float = 30
    speech_max_audio_mb: float = 10
    speech_max_duration_seconds: int = 120
    speech_language: str = "en"
    staff_email: str | None = None
    staff_password: str | None = None
    allowed_email_domains: tuple = ()
    sla_high_hours: float = 8.0
    sla_medium_hours: float = 48.0
    sla_low_hours: float = 120.0
    sla_critical_minutes: float = 30.0
    alert_smtp_host: str | None = None
    alert_smtp_port: int = 587
    alert_smtp_username: str | None = None
    alert_smtp_password: str | None = None
    alert_email_from: str | None = None
    alert_smtp_timeout: float = 10.0
    default_worker_phone: str = "+916398758826"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_from_phone: str | None = None
    alert_sms_timeout: float = 8.0
    rate_analyses_per_hour: int = 12
    rate_reports_per_day: int = 15
    log_level: str = "INFO"
    upload_dir: str = "uploads"
    signoff_days: float = 7.0
    demo_mode: bool = False
    campus_locations: tuple = ("Hostel Block B (Boys)", "Hostel C-Wing", "Central Library 2F", "Mess Hall", "Academic Complex Block A")
    agent_max_turns: int = 4
    agent_max_tool_calls: int = 8
    agent_max_tool_calls_per_turn: int = 3
    agent_max_history_messages: int = 8
    agent_timeout_seconds: float = 30


def _num(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default  # a typo in .env should not crash the app


def get_settings() -> Settings:
    """Read on every call so tests and Streamlit secrets can override."""
    return Settings(
        api_key=os.getenv("LLM_API_KEY") or None,
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        db_path=os.getenv("DB_PATH", "resolveai.db"),
        dup_threshold=_num("DUP_THRESHOLD", 45),
        ai_timeout=_num("LLM_TIMEOUT_SECONDS", 20),
        speech_api_key=os.getenv("SPEECH_API_KEY") or os.getenv("LLM_API_KEY") or None,
        speech_base_url=os.getenv("SPEECH_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        speech_model=os.getenv("SPEECH_MODEL", "whisper-large-v3-turbo"),
        speech_timeout=max(1.0, _num("SPEECH_TIMEOUT_SECONDS", 30)),
        speech_max_audio_mb=max(0.1, _num("SPEECH_MAX_AUDIO_MB", 10)),
        speech_max_duration_seconds=max(1, int(_num("SPEECH_MAX_DURATION_SECONDS", 120))),
        speech_language=os.getenv("SPEECH_LANGUAGE", "en").strip().lower() or "en",
        staff_email=os.getenv("STAFF_EMAIL") or None,
        staff_password=os.getenv("STAFF_PASSWORD") or None,
        sla_high_hours=_num("SLA_HIGH_HOURS", 8),
        sla_medium_hours=_num("SLA_MEDIUM_HOURS", 48),
        sla_low_hours=_num("SLA_LOW_HOURS", 120),
        sla_critical_minutes=max(1.0, _num("SLA_CRITICAL_MINUTES", 30)),
        alert_smtp_host=os.getenv("ALERT_SMTP_HOST") or None,
        alert_smtp_port=int(_num("ALERT_SMTP_PORT", 587)),
        alert_smtp_username=os.getenv("ALERT_SMTP_USERNAME") or None,
        alert_smtp_password=os.getenv("ALERT_SMTP_PASSWORD") or None,
        alert_email_from=os.getenv("ALERT_EMAIL_FROM") or os.getenv("ALERT_SMTP_USERNAME") or None,
        alert_smtp_timeout=max(1.0, _num("ALERT_SMTP_TIMEOUT", 10)),
        default_worker_phone=os.getenv("DEFAULT_WORKER_PHONE", "+916398758826").strip(),
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        twilio_messaging_service_sid=os.getenv("TWILIO_MESSAGING_SERVICE_SID") or None,
        twilio_from_phone=os.getenv("TWILIO_FROM_PHONE") or None,
        alert_sms_timeout=max(1.0, _num("ALERT_SMS_TIMEOUT", 8)),
        rate_analyses_per_hour=int(_num("RATE_ANALYSES_PER_HOUR", 12)),
        rate_reports_per_day=int(_num("RATE_REPORTS_PER_DAY", 15)),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        upload_dir=os.getenv("UPLOAD_DIR", "uploads"),
        signoff_days=_num("SIGNOFF_DAYS", 7),
        demo_mode=os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes"),
        campus_locations=tuple(x.strip() for x in os.getenv("CAMPUS_LOCATIONS", "").split(",") if x.strip()) or Settings.campus_locations,
        allowed_email_domains=tuple(d.strip().lower().lstrip("@") for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",") if d.strip()),
        agent_max_turns=max(1, min(8, int(_num("AGENT_MAX_TURNS", 4)))),
        agent_max_tool_calls=max(1, min(20, int(_num("AGENT_MAX_TOOL_CALLS", 8)))),
        agent_max_tool_calls_per_turn=max(1, min(5, int(_num("AGENT_MAX_TOOL_CALLS_PER_TURN", 3)))),
        agent_max_history_messages=max(0, min(20, int(_num("AGENT_MAX_HISTORY_MESSAGES", 8)))),
        agent_timeout_seconds=max(1, min(120, _num("AGENT_TIMEOUT_SECONDS", 30))),
    )
