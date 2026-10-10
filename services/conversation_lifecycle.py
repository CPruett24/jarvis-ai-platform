"""Active voice-discussion boundaries, independent of persisted sessions."""

from services.conversation_manager import clear_topic, clear_pending_request, clear_context
from services.conversation_service import clear_history


CONVERSATION_END_PHRASES = {
    "that's all", "thank you", "thanks", "goodbye", "never mind",
    "nevermind", "i'm done", "im done",
}

# A control result, distinct from generated text and tool responses.
CONVERSATION_ENDED = object()


def is_conversation_end(command):
    return command.lower().strip().rstrip(".,!?") in CONVERSATION_END_PHRASES


def reset_active_conversation():
    """Idempotently discard only process-local discussion state."""
    clear_history()
    clear_topic()
    clear_pending_request()
    clear_context()


def handle_conversation_boundary(reason):
    if reason in {"startup", "explicit_end", "exit"}:
        reset_active_conversation()
    elif reason != "timeout":
        raise ValueError(f"Unknown conversation boundary: {reason}")
