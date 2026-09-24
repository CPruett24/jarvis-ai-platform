import os

from dotenv import load_dotenv

from services.tts.elevenlabs_provider import (
    ElevenLabsTTSProvider,
)
from services.tts.local_provider import LocalTTSProvider


def create_tts_provider():
    """
    Create the configured JARVIS TTS provider.

    Falls back to local TTS when ElevenLabs is selected
    but cannot be initialized.
    """

    load_dotenv()

    provider_name = os.getenv(
        "JARVIS_TTS_PROVIDER",
        "local",
    ).strip().lower()

    if provider_name == "elevenlabs":
        try:
            return ElevenLabsTTSProvider(
                api_key=os.getenv(
                    "ELEVENLABS_API_KEY"
                ),
                voice_id=os.getenv(
                    "ELEVENLABS_VOICE_ID"
                ),
            )

        except Exception as exc:
            print(
                "[TTS] ElevenLabs unavailable. "
                f"Using local TTS: {exc}"
            )

            return LocalTTSProvider()

    return LocalTTSProvider()