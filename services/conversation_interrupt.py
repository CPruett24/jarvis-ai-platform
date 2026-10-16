"""Bounded interruption handoff; audio callbacks never perform native stop."""
import threading
from services.voice_diagnostics import voice_trace


class ConversationInterruptController:
    def __init__(self, speech):
        self.speech = speech
        self.lock = threading.Lock()
        self.interrupted = threading.Event()
        self.interrupted_text = None
        self.state = "listening"
        self.followup = None
        self.end_text = None

    def handle_speech(self, text):
        text = (text or "").strip()
        if not text:
            return
        from services.conversation_lifecycle import is_conversation_end
        end_control = is_conversation_end(text)
        with self.lock:
            if self.state == "handed_off":
                voice_trace("interruption_rejected", reason="closed_window")
                return
            if not self.interrupted.is_set():
                self.interrupted_text = text
                self.interrupted.set()
                self.state = "cancelling"
                voice_trace("interruption_transition", state=self.state)
                reason = "first_transcript"
            elif end_control:
                reason = "end_priority"
            elif self.end_text:
                voice_trace("interruption_rejected", reason="end_already_selected")
                return
            elif self.followup is None:
                # One subsequent complete utterance supersedes the initial
                # transcript. Further fragments are never concatenated/replayed.
                self.followup = text
                reason = "supersedes_initial"
            else:
                voice_trace("interruption_rejected", reason="handoff_capacity")
                return
            if end_control:
                self.end_text = text  # End controls have priority and are sticky.
            voice_trace("interruption_accepted", reason=reason, state=self.state)

    def begin_handoff(self):
        with self.lock:
            if self.state == "cancelling":
                self.state = "handoff_pending"
                voice_trace("interruption_transition", state=self.state)

    def was_interrupted(self):
        return self.interrupted.is_set()

    def get_interrupted_text(self):
        with self.lock:
            return self.end_text or self.followup or self.interrupted_text

    def handoff(self):
        with self.lock:
            self.state = "handed_off"
            voice_trace("interruption_transition", state=self.state)
            return self.end_text or self.followup or self.interrupted_text

    def reset(self):
        with self.lock:
            self.interrupted_text = self.followup = self.end_text = None
            self.interrupted = threading.Event()
            self.state = "listening"
