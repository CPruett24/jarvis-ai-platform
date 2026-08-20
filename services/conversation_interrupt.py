import threading


class ConversationInterruptController:
    """
    Coordinates microphone interruption with the current
    ConversationSpeech instance.
    """

    def __init__(self, speech):
        self.speech = speech

        self.lock = threading.Lock()

        self.interrupted_text = None
        self.interrupted = threading.Event()

    def handle_speech(self, text):
        if not text:
            return

        text = text.strip()

        if not text:
            return

        with self.lock:
            if self.interrupted.is_set():
                return

            # Capture the user's words BEFORE doing anything
            # that could block or race with the streaming thread.
            self.interrupted_text = text
            self.interrupted.set()

        print(
            "[Interrupt controller] "
            f"Captured interruption: {text}"
        )

        # Stop TTS after the interruption has been recorded.
        self.speech.interrupt()

    def was_interrupted(self):
        return self.interrupted.is_set()

    def get_interrupted_text(self):
        with self.lock:
            return self.interrupted_text

    def reset(self):
        with self.lock:
            self.interrupted_text = None
            self.interrupted.clear()