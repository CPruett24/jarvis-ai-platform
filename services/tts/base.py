from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """
    Interface implemented by JARVIS text-to-speech providers.
    """

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