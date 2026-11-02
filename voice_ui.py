"""Shared multilingual dictation control for authenticated ticket workspaces."""
import streamlit as st

from config import get_settings
from rate_limit import RateLimitError, check as rate_check
from voice_service import SPEECH_LANGUAGES, VoiceError, transcribe_audio


def render_voice_dictation(*, target_key: str, key: str, user_id: int) -> None:
    """Offer microphone dictation that fills an existing Streamlit text-area value."""
    settings = get_settings()
    with st.expander("🎙️ Dictate this note", expanded=False):
        st.caption("Choose the spoken language. Audio is sent to the configured speech service only when you select Transcribe; ResolveAI does not keep the recording.")
        language = st.selectbox("Spoken language", list(SPEECH_LANGUAGES), key=f"{key}_language")
        audio = st.audio_input("Record a voice note", sample_rate=16000, key=f"{key}_audio", disabled=not settings.speech_api_key)
        if not settings.speech_api_key:
            st.info("Voice transcription is unavailable until SPEECH_API_KEY or LLM_API_KEY is configured.")
        if audio is not None and st.button("Transcribe into note", key=f"{key}_transcribe", type="secondary", disabled=not settings.speech_api_key):
            try:
                rate_check(user_id, "speech", settings.rate_analyses_per_hour, 60)
                with st.spinner("Transcribing your note…"):
                    transcript = transcribe_audio(audio.getvalue(), language=SPEECH_LANGUAGES[language], settings=settings)
                st.session_state[target_key] = transcript
                st.success("Transcript added. Review it before saving.")
            except (VoiceError, RateLimitError) as exc:
                st.error(str(exc))
