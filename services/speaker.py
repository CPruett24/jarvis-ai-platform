import threading

from services.status_service import (
    update_status,
    update_last_response,
)
from services.tts.factory import create_tts_provider
from services.voice_diagnostics import voice_trace
from services.tts.outcome import PlaybackOutcome, playback_outcome


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
        self.stop_worker = None
        self.cancellation = threading.Event()

    def speak(self, text):
        if not text:
            return PlaybackOutcome.SKIPPED

        print(f"JARVIS: {text}")
        update_last_response(text)

        with self.lock:
            if self.speaking or (self.stop_worker and self.stop_worker.is_alive()):
                print("[TTS] Playback is still recovering; response remains available as text.")
                return PlaybackOutcome.SKIPPED
            self.speaking = True
            cancellation = self.cancellation = threading.Event()

        update_status("speaking")

        try:
            cancellable = getattr(self.provider, "speak_cancellable", None)
            if cancellable:
                result = playback_outcome(cancellable(text, cancellation))
            elif not cancellation.is_set():
                result = playback_outcome(self.provider.speak(text))
            else:
                result = PlaybackOutcome.INTERRUPTED
            return PlaybackOutcome.INTERRUPTED if cancellation.is_set() else result

        except Exception as error:
            print(f"[TTS] Speech failed ({type(error).__name__}).")
            return PlaybackOutcome.INTERRUPTED if cancellation.is_set() else PlaybackOutcome.FAILED

        finally:
            with self.lock:
                self.speaking = False

            update_status("listening")

    def stop(self):
        """
        Immediately stop the current TTS provider.
        """

        with self.lock:
            if self.cancellation.is_set():
                return
            self.cancellation.set()
            if self.stop_worker and self.stop_worker.is_alive():
                return
            self.stop_worker = threading.Thread(
                target=self._stop_provider, name="jarvis-provider-stop", daemon=True,
            )
            self.stop_worker.start()
        # Quick providers finish here; a native stop cannot strand the caller.
        self.stop_worker.join(timeout=0.02)

    def _stop_provider(self):
        voice_trace("provider_stop_entry")
        try:
            self.provider.stop()
        except Exception as error:
            print(f"[TTS] Stop failed ({type(error).__name__}).")
        finally:
            voice_trace("provider_stop_exit")

    def is_speaking(self):
        with self.lock:
            return self.speaking


_default_speaker = InterruptibleSpeaker()


def speak(text):
    return _default_speaker.speak(text)


def stop_speaking():
    _default_speaker.stop()


def is_speaking():
    return _default_speaker.is_speaking()
