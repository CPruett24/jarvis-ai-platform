"""Runtime fallback without changing the configured provider's normal voice."""

import threading

from services.tts.base import TTSProvider
from services.tts.outcome import PlaybackOutcome, playback_outcome
from services.voice_diagnostics import voice_trace


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
        self.stop_requested = False

    def _speak_with(self, provider, text):
        with self.state_lock:
            if self.cancelled.is_set():
                return PlaybackOutcome.INTERRUPTED
            self.active = provider
            self.stop_requested = False
        try:
            cancellable = getattr(provider, "speak_cancellable", None)
            if cancellable:
                return playback_outcome(cancellable(text, self.cancelled))
            elif not self.cancelled.is_set():
                return playback_outcome(provider.speak(text))
            return PlaybackOutcome.INTERRUPTED
        finally:
            with self.state_lock:
                self.active = None

    def speak(self, text):
        return self.speak_cancellable(text, threading.Event())

    def speak_cancellable(self, text, cancellation_event):
        if not text:
            return PlaybackOutcome.SKIPPED
        # Keep utterances ordered while allowing stop() to reach active playback.
        with self.speech_lock:
            with self.state_lock:
                self.cancelled = cancellation_event
            if self.cancelled.is_set():
                return PlaybackOutcome.INTERRUPTED
            if not self.quota_exhausted:
                try:
                    return self._speak_with(self.primary, text)
                except Exception as error:
                    if _quota_exceeded(error):
                        self.quota_exhausted = True
                        print("[TTS] ElevenLabs quota exceeded; using local TTS for this run.")
                    elif not self.cancelled.is_set():
                        print(f"[TTS] ElevenLabs unavailable ({type(error).__name__}); using local TTS.")
            if self.cancelled.is_set():
                return PlaybackOutcome.INTERRUPTED
            try:
                return self._speak_with(self.fallback, text)
            except Exception as error:
                if not self.cancelled.is_set():
                    print(f"[TTS] Local speech failed ({type(error).__name__}).")
                return (PlaybackOutcome.INTERRUPTED if self.cancelled.is_set()
                        else PlaybackOutcome.FAILED)

    def stop(self):
        voice_trace("fallback_stop_entry")
        with self.state_lock:
            self.cancelled.set()
            active = self.active
            if self.stop_requested:
                return
            self.stop_requested = True
        if active is not None:
            try:
                active.stop()
            except Exception as error:
                print(f"[TTS] Could not stop playback ({type(error).__name__}).")
        voice_trace("fallback_stop_exit")
