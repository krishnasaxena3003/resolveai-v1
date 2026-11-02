import io
import json
import wave
from types import SimpleNamespace

import pytest
from conftest import FakeClient
from ai_service import fallback_analysis
from config import get_settings
from schemas import Status
from ticket_service import create_ticket, list_tickets
from voice_service import VoiceError, transcribe_audio, validate_audio
from workflow import finalize_submission, prepare_submission


def wav_bytes(seconds=2):
    data = io.BytesIO()
    with wave.open(data, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\0\0" * 16000 * seconds)
    return data.getvalue()


def settings(**overrides):
    values = dict(speech_api_key="test-key", speech_base_url="https://speech.test/v1", speech_model="whisper-large-v3-turbo",
                  speech_timeout=5, speech_max_audio_mb=10, speech_max_duration_seconds=120, speech_language="en")
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeTranscriptions:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.result)


def speech_client(result=None, error=None):
    transcriptions = FakeTranscriptions(result, error)
    return SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions)), transcriptions


def test_speech_settings_reuse_llm_key_and_allow_separate_credentials(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("SPEECH_API_KEY", raising=False)
    monkeypatch.delenv("SPEECH_MODEL", raising=False)
    settings_ = get_settings()
    assert settings_.speech_api_key == "llm-key" and settings_.speech_model == "whisper-large-v3-turbo"
    monkeypatch.setenv("SPEECH_API_KEY", "speech-key")
    assert get_settings().speech_api_key == "speech-key"


def test_valid_audio_is_measured_and_transcript_is_normalized():
    audio = wav_bytes()
    info = validate_audio(audio, settings=settings())
    assert info.duration_seconds == 2 and info.size_bytes == len(audio)
    client, endpoint = speech_client("  No electricity\n in Hostel Block B.  ")
    assert transcribe_audio(audio, client=client, settings=settings()) == "No electricity in Hostel Block B."
    assert endpoint.kwargs["model"] == "whisper-large-v3-turbo"
    assert endpoint.kwargs["language"] == "en" and endpoint.kwargs["response_format"] == "json"


@pytest.mark.parametrize("audio, message", [(b"", "No recording"), (b"not audio", "format is not supported"), (b"RIFFbad!WAVE", "could not be read")])
def test_empty_and_unsupported_audio_are_rejected(audio, message):
    with pytest.raises(VoiceError, match=message):
        validate_audio(audio, settings=settings())


def test_audio_size_and_duration_limits_are_checked_before_api_call():
    with pytest.raises(VoiceError, match="larger than"):
        validate_audio(wav_bytes(), settings=settings(speech_max_audio_mb=0.001))
    with pytest.raises(VoiceError, match="under 1 seconds"):
        validate_audio(wav_bytes(2), settings=settings(speech_max_duration_seconds=1))


def test_empty_transcript_timeout_provider_failure_and_missing_key_are_safe():
    audio = wav_bytes()
    client, _ = speech_client(" \n ")
    with pytest.raises(VoiceError, match="couldn't hear clear speech"):
        transcribe_audio(audio, client=client, settings=settings())

    client, _ = speech_client(error=TimeoutError())
    with pytest.raises(VoiceError, match="took too long"):
        transcribe_audio(audio, client=client, settings=settings())

    client, _ = speech_client(error=RuntimeError("provider details should not leak"))
    with pytest.raises(VoiceError, match="couldn't transcribe") as error:
        transcribe_audio(audio, client=client, settings=settings())
    assert "provider details" not in str(error.value)

    with pytest.raises(VoiceError, match="not configured"):
        transcribe_audio(audio, client=object(), settings=settings(speech_api_key=None))

    client, _ = speech_client("x" * 1001)
    with pytest.raises(VoiceError, match="longer than the report field"):
        transcribe_audio(audio, client=client, settings=settings())


def test_transcription_alone_creates_no_ticket_and_reviewed_text_uses_existing_flow(db):
    original = "The hallway light near Hostel Block B is not working."
    existing = create_ticket(fallback_analysis(original), original, "Hostel Block B", "fallback", db_path=db)
    client, _ = speech_client(original)
    transcript = transcribe_audio(wav_bytes(), client=client, settings=settings())
    assert [t.ticket_id for t in list_tickets(db_path=db)] == [existing.ticket.ticket_id]

    reviewed = transcript + " It has been dark since this morning."
    triage = FakeClient([json.dumps({"summary": "Hallway light out", "category": "Electricity", "priority": "Medium"})])
    prepared = prepare_submission(reviewed, "Hostel Block B", client=triage, db_path=db)
    assert prepared.candidates and prepared.candidates[0].ticket_id == existing.ticket.ticket_id
    created = finalize_submission(prepared, link_to=existing.ticket.ticket_id, db_path=db)
    assert created.ticket.description == reviewed and created.ticket.duplicate_of == existing.ticket.ticket_id
    assert created.ticket.status == Status.OPEN
