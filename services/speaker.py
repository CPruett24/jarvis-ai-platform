import threading

import pyttsx3

from services.status_service import (
    update_status,
    update_last_response,
)
import time

class InterruptibleSpeaker:
    """
    Thread-safe speaker that can immediately stop the
    currently playing pyttsx3 response.
    """

    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()
        self.speaking = False

    def speak(self, text):
        if not text:
            return

        print(f"JARVIS: {text}")

        update_status("speaking")
        update_last_response(text)

        tts_started = time.perf_counter()

        engine = pyttsx3.init()

        tts_initialized = time.perf_counter()

        print(
            "[Voice timing] "
            f"tts_init="
            f"{tts_initialized - tts_started:.2f}s"
        )

        with self.lock:
            self.engine = engine
            self.speaking = True
        try:
            engine.say(text)
            engine.runAndWait()

        finally:

            try:
                engine.stop()
            except Exception:
                pass

            with self.lock:

                if self.engine is engine:
                    self.engine = None

                self.speaking = False

            update_status("listening")

    def stop(self):
        """
        Immediately stop the currently playing response.
        """

        with self.lock:
            engine = self.engine

        if engine is None:
            return

        try:
            engine.stop()
        except Exception:
            pass

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