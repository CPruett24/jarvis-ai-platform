from abc import ABC, abstractmethod
from services.tts.outcome import PlaybackOutcome, playback_outcome


class TTSProvider(ABC):
    """
    Interface implemented by JARVIS text-to-speech providers.
    """

    def speak_cancellable(self, text, cancellation_event):
        """Optional operation signal; native providers may override registration."""
        if not cancellation_event.is_set():
            result = playback_outcome(self.speak(text))
            return PlaybackOutcome.INTERRUPTED if cancellation_event.is_set() else result
        return PlaybackOutcome.INTERRUPTED

    @abstractmethod
    def speak(self, text):
        """
        Speak text and block until playback finishes
        or is interrupted.
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """
        Stop the provider's current playback.
        """
        raise NotImplementedError
