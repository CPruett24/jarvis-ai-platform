from contextlib import contextmanager
from contextvars import ContextVar
import threading

from services.conversation_db import save_message, get_recent_messages
from services.tts.outcome import PlaybackOutcome, playback_outcome
from services.voice_diagnostics import voice_trace

conversation_history = []
_response_delivery = ContextVar("response_delivery", default=None)


class ResponseDelivery:
    """Operation-scoped receipt; never locate an answer by text or global tail."""
    def __init__(self):
        self.lock = threading.Lock()
        self.records = []
        self.status = "unknown"

    def record(self, entry, record_id):
        with self.lock:
            self.records.append((entry, record_id))
            self._update(entry, record_id)

    def _update(self, entry, record_id):
        entry["playback_status"] = self.status
        if record_id is not None:
            from services.conversation_db import update_playback_status
            try:
                update_playback_status(record_id, self.status)
            except Exception as error:
                print(f"[Conversation] Playback status save failed ({type(error).__name__}).")

    def finish(self, result):
        status = playback_outcome(result)
        if status == PlaybackOutcome.SKIPPED:
            status = PlaybackOutcome.FAILED
        with self.lock:
            self.status = status.value
            for entry, record_id in self.records:
                self._update(entry, record_id)
        voice_trace("playback_final", outcome=self.status, records=len(self.records))


@contextmanager
def capture_response_delivery(receipt):
    token = _response_delivery.set(receipt)
    try:
        yield receipt
    finally:
        _response_delivery.reset(token)

def restore_recent_history(
    limit=10,
):

    messages = get_recent_messages(
        limit=limit
    )

    conversation_history.clear()

    for message in messages:

        conversation_history.append(
            {
                "role": message["role"],
                "content": message["content"],
                "source": message.get("source"),
            }
        )

def add_message(
    role,
    message,
    source=None,
):

    entry = {
        "role": role,
        "content": message,
        "source": source,
    }

    conversation_history.append(entry)

    try:
        record_id = save_message(
            role,
            message,
            source=source,
        )

    except Exception as e:
        print(f"Conversation save failed: {e}")
        record_id = None

    receipt = _response_delivery.get()
    if role == "assistant" and receipt is not None:
        receipt.record(entry, record_id)
    return entry


def get_conversation_history():
    return conversation_history


def get_history():
    return conversation_history[-10:]

def get_source_aware_history(
    limit=10,
):

    history = conversation_history[
        -limit:
    ]

    formatted_history = []

    for message in history:

        role = message["role"]
        content = message["content"]
        source = message.get("source")

        if source == "hermes":

            if content.startswith(
                "[agent_result]"
            ):

                content = (
                    "External agent result:\n"
                    f"{content}"
                )

            else:

                content = (
                    "Hermes research result:\n"
                    f"{content}"
                )

        elif source == "router":

            content = (
                "JARVIS system response:\n"
                f"{content}"
            )

        elif source == "observed":

            content = (
                "Observed tool result:\n"
                f"{content}"
            )

        elif source == "historical_recall":

            content = (
                "Historical conversation recap (derived from saved excerpts; "
                "not verified personal facts):\n"
                f"{content}"
            )

        elif source and source not in (
            "user",
            "ollama",
        ):

            content = (
                f"External source ({source}) result:\n"
                f"{content}"
            )

        formatted_history.append(
            {
                "role": role,
                "content": content,
            }
        )

    return formatted_history

def clear_history():
    conversation_history.clear()
