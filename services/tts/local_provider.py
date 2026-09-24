import threading

import pyttsx3

from services.tts.base import TTSProvider


class LocalTTSProvider(TTSProvider):
    """
    Local pyttsx3 text-to-speech provider.
    """

    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()

    def speak(self, text):
        if not text:
            return

        engine = pyttsx3.init()

        with self.lock:
            self.engine = engine

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

    def stop(self):
        with self.lock:
            engine = self.engine

        if engine is None:
            return

        try:
            engine.stop()
        except Exception:
            pass