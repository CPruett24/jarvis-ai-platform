import threading

import pytest

from commands import router
from services import ai_service
from services.agents.hermes_acp import HermesACPConnection
from services.cancellation import OperationCancelled, check_cancelled
from services.conversation_interrupt import ConversationInterruptController


class Speech:
    def interrupt(self):
        pass


def test_signal_is_operation_scoped_and_reset_does_not_revive_old_work():
    controller = ConversationInterruptController(Speech())
    old_signal = controller.interrupted

    check_cancelled(old_signal)

    controller.handle_speech("stop")

    with pytest.raises(OperationCancelled):
        check_cancelled(old_signal)

    controller.reset()

    check_cancelled(controller.interrupted)
    assert old_signal.is_set()

    check_cancelled(
        ConversationInterruptController(Speech()).interrupted
    )


def test_cancelled_ai_stream_does_not_record_success_and_next_stream_is_fresh(
    monkeypatch,
):
    saved = []
    statuses = []
    closed = []
    calls = []
    event = threading.Event()

    class OllamaStream:
        def __init__(self, name):
            self.name = name
            self.items = iter([
                {"message": {"content": "first"}},
                {"message": {"content": "late"}},
            ])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.items)

        def close(self):
            closed.append(self.name)

    def chat(**kwargs):
        name = str(len(calls))
        calls.append(kwargs)
        return OllamaStream(name)

    monkeypatch.setattr(
        ai_service,
        "chat",
        chat,
    )
    monkeypatch.setattr(
        ai_service,
        "_build_conversation_messages",
        lambda: [],
    )
    monkeypatch.setattr(
        ai_service,
        "add_message",
        lambda *args, **kwargs: saved.append(
            (args, kwargs)
        ),
    )
    monkeypatch.setattr(
        ai_service,
        "update_status",
        statuses.append,
    )

    stream = ai_service.stream_ai_response(
        "old",
        cancellation_event=event,
    )

    assert next(stream) == "first"

    event.set()

    with pytest.raises(OperationCancelled):
        next(stream)

    assert saved == [
        (
            ("user", "old"),
            {"source": "user"},
        ),
    ]

    assert statuses == ["thinking"]
    assert closed == ["0"]

    fresh_event = threading.Event()

    assert list(
        ai_service.stream_ai_response(
            "new",
            cancellation_event=fresh_event,
        )
    ) == ["first", "late"]

    assert saved[-1] == (
        ("assistant", "firstlate"),
        {"source": "ollama"},
    )

    assert statuses[-1] == "listening"
    assert closed == ["0", "1"]

    assert list(
        ai_service.stream_ai_response(
            "again",
            cancellation_event=threading.Event(),
        )
    ) == ["first", "late"]

    assert len(calls) == 3
    assert closed == ["0", "1", "2"]


def test_precancelled_stream_does_not_start_provider(
    monkeypatch,
):
    event = threading.Event()
    event.set()

    monkeypatch.setattr(
        ai_service,
        "add_message",
        lambda *a, **k: pytest.fail(
            "Must not start"
        ),
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        lambda **kwargs: pytest.fail(
            "Provider must not start"
        ),
    )

    with pytest.raises(OperationCancelled):
        list(
            ai_service.stream_ai_response(
                "hello",
                cancellation_event=event,
            )
        )


def test_acp_local_wait_cancels_without_claiming_remote_request_stopped(
    monkeypatch,
):
    connection = HermesACPConnection(
        executable="unused"
    )

    started = threading.Event()
    release = threading.Event()
    worker_done = threading.Event()
    consumer_done = threading.Event()

    cancellation = threading.Event()
    errors = []

    def request(*args, **kwargs):
        started.set()

        try:
            assert release.wait(2)
        finally:
            worker_done.set()

    monkeypatch.setattr(
        connection,
        "_send_request",
        request,
    )

    def consume():
        try:
            list(
                connection.stream_prompt(
                    "session",
                    "hello",
                    cancellation_event=cancellation,
                )
            )
        except OperationCancelled as exc:
            errors.append(exc)
        finally:
            consumer_done.set()

    thread = threading.Thread(
        target=consume
    )

    thread.start()

    try:
        assert started.wait(1)

        cancellation.set()

        assert consumer_done.wait(1)
        assert len(errors) == 1

        # Cancellation stops local consumption. It does
        # not claim that the remote request stopped.
        assert not worker_done.is_set()

        assert (
            connection._notification_handlers
            == []
        )

    finally:
        release.set()

        thread.join(2)

        assert worker_done.wait(1)


def test_permission_denial_still_returns_cancelled_outcome(
    monkeypatch,
):
    connection = HermesACPConnection(
        executable="unused"
    )

    sent = []

    monkeypatch.setattr(
        connection,
        "_write_jsonrpc",
        sent.append,
    )

    connection._handle_server_request({
        "id": "permission",
        "method": "session/request_permission",
    })

    assert sent[0]["result"] == {
        "outcome": {
            "outcome": "cancelled",
        }
    }


def test_router_passes_controller_signal_and_producer_exits(
    monkeypatch,
):
    controller = ConversationInterruptController(
        Speech()
    )

    started = threading.Event()
    stopped = threading.Event()

    def stream(
        command,
        cancellation_event,
    ):
        assert (
            cancellation_event
            is controller.interrupted
        )

        started.set()

        try:
            assert cancellation_event.wait(1)

            check_cancelled(
                cancellation_event
            )

            yield "must not be emitted"

        finally:
            stopped.set()

    monkeypatch.setattr(
        router,
        "stream_ai_response",
        stream,
    )

    result = []

    consumer = threading.Thread(
        target=lambda: result.extend(
            router._stream_with_interrupt(
                "hello",
                controller,
            )
        )
    )

    consumer.start()

    try:
        assert started.wait(1)

        controller.handle_speech("stop")

        assert stopped.wait(1)

        consumer.join(1)

        assert not consumer.is_alive()
        assert result == []

    finally:
        controller.interrupted.set()

        consumer.join(2)