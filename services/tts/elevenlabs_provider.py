import threading
import time

import pyaudio
from elevenlabs.client import ElevenLabs

from services.tts.base import TTSProvider


class ElevenLabsTTSProvider(TTSProvider):
    """
    ElevenLabs streaming TTS provider using raw PCM playback.
    """

    SAMPLE_RATE = 24000

    def __init__(
        self,
        api_key,
        voice_id,
        model_id="eleven_flash_v2_5",
        client=None,
        audio_factory=None,
    ):
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is required."
            )

        if not voice_id:
            raise ValueError(
                "ELEVENLABS_VOICE_ID is required."
            )

        self.voice_id = voice_id
        self.model_id = model_id

        self.client = (
            client
            if client is not None
            else ElevenLabs(api_key=api_key)
        )

        self.audio_factory = (
            audio_factory
            if audio_factory is not None
            else pyaudio.PyAudio
        )

        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.audio_stream = None

    def speak(self, text):
        if not text:
            return

        self.stop_event.clear()

        request_started = time.perf_counter()

        audio = self.audio_factory()
        stream = None

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.SAMPLE_RATE,
                output=True,
            )

            with self.lock:
                self.audio_stream = stream

            response = self.client.text_to_speech.stream(
                voice_id=self.voice_id,
                output_format="pcm_24000",
                text=text,
                model_id=self.model_id,
            )

            first_audio = True

            for chunk in response:
                if self.stop_event.is_set():
                    break

                if not chunk:
                    continue

                if first_audio:
                    first_audio = False

                    print(
                        "[Voice timing] "
                        "elevenlabs_first_audio="
                        f"{time.perf_counter() - request_started:.2f}s"
                    )

                stream.write(chunk)

        finally:
            with self.lock:
                self.audio_stream = None

            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

            try:
                audio.terminate()
            except Exception:
                pass

    def stop(self):
        self.stop_event.set()

        with self.lock:
            stream = self.audio_stream

        if stream is None:
            return

        try:
            stream.stop_stream()
        except Exception:
            pass