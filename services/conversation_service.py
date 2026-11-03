from contextlib import contextmanager
from contextvars import ContextVar
import threading

from services.conversation_db import save_message, get_recent_messages
from services.tts.outcome import PlaybackOutcome, playback_outcome
from services.voice_diagnostics import voice_trace

conversation_history = []
_response_delivery = ContextVar("response_delivery", default=None)
_delivery_lock = threading.RLock()
_active_delivery = None
_delivery_generation = 0


def current_response_delivery():
    return _response_delivery.get()


def supersede_guarded_delivery():
    """A new routed command also supersedes C3 when it needs no own receipt."""
    global _active_delivery
    with _delivery_lock:
        previous = _active_delivery
        if previous is not None and previous.guarded:
            _active_delivery = None
        else:
            previous = None
    if previous is not None:
        previous.cancel()


class ResponseDelivery:
    """Operation-scoped receipt; never locate an answer by text or global tail."""
    def __init__(self, cancellation_event=None):
        self.lock = threading.Lock()
        self.records = []
        self.status = "unknown"
        self.cancellation_event = cancellation_event or threading.Event()
        self.closed = False
        self.publication = None
        self.prepared_publication = None
        self.publication_identity = None
        self.guarded = False
        self.cancel_callback = None
        self.playback_guard = None
        from services import conversation_db
        self.session = conversation_db.current_session
        self.generation = _delivery_generation
        self.consumer_thread = threading.get_ident()

    def activate(self):
        global _active_delivery
        with _delivery_lock:
            if self.guarded:
                self.check_current()
            previous = _active_delivery
            _active_delivery = self
        if previous is not None and previous is not self and previous.guarded:
            previous.cancel()

    def cancel(self):
        self.cancellation_event.set()
        if self.cancel_callback is not None:
            self.cancel_callback()

    def check_current(self, *, consumer=False):
        from services import conversation_db
        from services.cancellation import OperationCancelled, check_cancelled
        check_cancelled(self.cancellation_event)
        with _delivery_lock:
            if (self.closed or _active_delivery is not self or self.generation != _delivery_generation
                    or self.session is not conversation_db.current_session
                    or consumer and (current_response_delivery() is not self
                                     or threading.get_ident() != self.consumer_thread)):
                raise OperationCancelled("Response receipt is superseded, closed or belongs to another session/consumer.")

    def claim_publication(self, publication):
        self.check_current(consumer=True)
        with _delivery_lock:
            if self.publication is not None:
                from services.cancellation import OperationCancelled
                raise OperationCancelled("Response publication receipt has already been consumed.")
            self.publication = publication

    def prepare_publication(self, publication, identity):
        """Bind one producer result to this operation before consumer admission."""
        self.check_current()
        with _delivery_lock:
            if self.prepared_publication is not None:
                from services.cancellation import OperationCancelled
                raise OperationCancelled("A response receipt already has a prepared publication.")
            self.prepared_publication = publication
            self.publication_identity = identity

    def guard_publication(self):
        with _delivery_lock:
            self.check_current()
            self.guarded = True

    def check_publication(self, publication):
        self.check_current()
        if self.publication is not publication:
            from services.cancellation import OperationCancelled
            raise OperationCancelled("Response publication receipt does not match.")

    @contextmanager
    def publication_window(self):
        """Serialize guarded history effects against session/request replacement."""
        with _delivery_lock:
            self.check_current(consumer=True)
            yield

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
        global _active_delivery
        status = playback_outcome(result)
        if status == PlaybackOutcome.SKIPPED:
            status = PlaybackOutcome.FAILED
        with self.lock:
            self.status = status.value
            for entry, record_id in self.records:
                self._update(entry, record_id)
        voice_trace("playback_final", outcome=self.status, records=len(self.records))
        with _delivery_lock:
            self.closed = True
            if _active_delivery is self:
                _active_delivery = None


@contextmanager
def capture_response_delivery(receipt):
    receipt.activate()
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
    global _delivery_generation
    with _delivery_lock:
        _delivery_generation += 1
        previous = _active_delivery
    if previous is not None and previous.guarded:
        previous.cancel()
    conversation_history.clear()
