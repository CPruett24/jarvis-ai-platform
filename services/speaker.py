import threading

from services.status_service import (
    update_status,
    update_last_response,
)
from services.tts.factory import create_tts_provider


class InterruptibleSpeaker:
    """
    Thread-safe speaker that delegates speech generation
    and playback to a replaceable TTS provider.
    """

    def __init__(self, provider=None):
        self.provider = (
            provider
            if provider is not None
            else create_tts_provider()
        )
        self.lock = threading.Lock()
        self.speaking = False

    def speak(self, text):
        if not text:
            return

        print(f"JARVIS: {text}")

        update_status("speaking")
        update_last_response(text)

        with self.lock:
            self.speaking = True

        try:
            self.provider.speak(text)

        finally:
            with self.lock:
                self.speaking = False

            update_status("listening")

    def stop(self):
        """
        Immediately stop the current TTS provider.
        """

        self.provider.stop()

        with self.lock:
            self.speaking = False

    def is_speaking(self):
        with self.lock:
            return self.speaking


_default_speaker = InterruptibleSpeaker()


def speak(text):
    _default_speaker.speak(text)


def stop_speaking():
    _default_speaker.stop()


def is_speaking():
    return _default_speaker.is_speaking()