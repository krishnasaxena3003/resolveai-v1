"""Browser-recorded WAV validation and speech-to-text, separate from complaint triage."""
from dataclasses import dataclass
from io import BytesIO
import logging
import re
import wave

from openai import OpenAI
from config import Settings, get_settings

log = logging.getLogger("resolveai.voice")
MAX_TRANSCRIPT_CHARS = 1000
SPEECH_LANGUAGES = {
    "Auto-detect": None,
    "English": "en", "Hindi": "hi", "Bengali": "bn", "Gujarati": "gu",
    "Kannada": "kn", "Malayalam": "ml", "Marathi": "mr", "Nepali": "ne",
    "Punjabi": "pa", "Tamil": "ta", "Telugu": "te", "Urdu": "ur",
    "Arabic": "ar", "French": "fr", "Spanish": "es",
}
_USE_CONFIG_LANGUAGE = object()


class VoiceError(ValueError):
    """A safe, user-facing message for invalid audio or transcription failure."""


@dataclass(frozen=True)
class AudioInfo:
    duration_seconds: float
    size_bytes: int


def validate_audio(audio: bytes | bytearray | memoryview, *, settings: Settings | None = None) -> AudioInfo:
    """Accept real PCM WAV recordings only; reject empty, oversized, malformed, and too-long audio."""
    s = settings or get_settings()
    data = bytes(audio or b"")
    if not data:
        raise VoiceError("No recording was received. Record a short message and try again.")
    if len(data) > s.speech_max_audio_mb * 1024 * 1024:
        raise VoiceError(f"That recording is larger than {s.speech_max_audio_mb:g} MB. Record a shorter message and try again.")
    if not (data.startswith(b"RIFF") and data[8:12] == b"WAVE"):
        raise VoiceError("This audio format is not supported. Please record again in your browser.")
    try:
        with wave.open(BytesIO(data), "rb") as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            channels, width = wav.getnchannels(), wav.getsampwidth()
            if rate <= 0 or frames <= 0 or channels not in (1, 2) or width not in (1, 2, 3, 4):
                raise VoiceError("The recording is empty or uses an unsupported audio format.")
            duration = frames / rate
    except VoiceError:
        raise
    except (wave.Error, EOFError, OSError) as exc:
        raise VoiceError("The recording could not be read. Please record it again.") from exc
    if duration < 0.25:
        raise VoiceError("The recording is too short to transcribe. Please record a little longer.")
    if duration > s.speech_max_duration_seconds:
        raise VoiceError(f"Keep recordings under {s.speech_max_duration_seconds} seconds and try again.")
    return AudioInfo(duration_seconds=duration, size_bytes=len(data))


def normalize_transcription(text: str | None) -> str:
    """Normalize whitespace without changing the student's words."""
    transcript = re.sub(r"\s+", " ", text or "").strip()
    if not transcript:
        raise VoiceError("We couldn't hear clear speech in that recording. Try again or type your report.")
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        raise VoiceError("That transcript is longer than the report field allows. Record a shorter message or type a concise summary.")
    return transcript


def transcribe_audio(audio: bytes | bytearray | memoryview, *, language: str | None | object = _USE_CONFIG_LANGUAGE, client=None, settings: Settings | None = None) -> str:
    """Transcribe browser WAV via the configured OpenAI-compatible speech endpoint.

    The raw audio is sent directly from memory to the provider and is never written to disk.
    """
    s = settings or get_settings()
    validate_audio(audio, settings=s)
    if not s.speech_api_key:
        raise VoiceError("Voice transcription is not configured. Ask an administrator to add SPEECH_API_KEY, or use the text field.")
    try:
        api = client or OpenAI(api_key=s.speech_api_key, base_url=s.speech_base_url, timeout=s.speech_timeout)
        options = {
            "file": ("complaint.wav", bytes(audio), "audio/wav"),
            "model": s.speech_model,
            "response_format": "json",
            "temperature": 0,
        }
        language_value = s.speech_language if language is _USE_CONFIG_LANGUAGE else language
        selected_language = (language_value or "").strip().lower()
        if selected_language:
            if selected_language not in {code for code in SPEECH_LANGUAGES.values() if code}:
                raise VoiceError("Choose a supported language or use Auto-detect.")
            options["language"] = selected_language
        result = api.audio.transcriptions.create(**options)
        return normalize_transcription(getattr(result, "text", ""))
    except VoiceError:
        raise
    except Exception as exc:
        error_name = type(exc).__name__
        log.warning("speech_transcription_failed", extra={"error_type": error_name})
        if "timeout" in error_name.lower():
            raise VoiceError("Transcription took too long. Check your connection and try again.") from exc
        if "connection" in error_name.lower():
            raise VoiceError("The transcription service could not be reached. Check your connection and try again.") from exc
        raise VoiceError("We couldn't transcribe that recording. Please try again or type your report.") from exc
