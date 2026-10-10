"""Runtime fallback without changing the configured provider's normal voice."""

import threading

from services.tts.base import TTSProvider


def _quota_exceeded(error):
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return False
    detail = body.get("detail", body)
    return isinstance(detail, dict) and (
        detail.get("status") == "quota_exceeded"
        or detail.get("code") == "quota_exceeded"
    )


class FallbackTTSProvider(TTSProvider):
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.quota_exhausted = False
        self.speech_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.cancelled = threading.Event()
        self.active = None

    def _speak_with(self, provider, text):
        with self.state_lock:
            if self.cancelled.is_set():
                return
            self.active = provider
        try:
            provider.speak(text)
        finally:
            with self.state_lock:
                self.active = None

    def speak(self, text):
        if not text:
            return
        # Keep utterances ordered while allowing stop() to reach active playback.
        with self.speech_lock:
            self.cancelled.clear()
            if not self.quota_exhausted:
                try:
                    self._speak_with(self.primary, text)
                    return
                except Exception as error:
                    if _quota_exceeded(error):
                        self.quota_exhausted = True
                        print("[TTS] ElevenLabs quota exceeded; using local TTS for this run.")
                    elif not self.cancelled.is_set():
                        print(f"[TTS] ElevenLabs unavailable ({type(error).__name__}); using local TTS.")
            if self.cancelled.is_set():
                return
            try:
                self._speak_with(self.fallback, text)
            except Exception as error:
                if not self.cancelled.is_set():
                    print(f"[TTS] Local speech failed ({type(error).__name__}).")

    def stop(self):
        with self.state_lock:
            self.cancelled.set()
            active = self.active
        if active is not None:
            try:
                active.stop()
            except Exception as error:
                print(f"[TTS] Could not stop playback ({type(error).__name__}).")
