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


@pytest.fixture(autouse=True)
def isolate_cached_session(monkeypatch):
    monkeypatch.setattr(ai_service, "_hermes_session_id", None)


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
    check_cancelled(ConversationInterruptController(Speech()).interrupted)


def test_cancelled_ai_stream_does_not_record_success_and_next_stream_is_fresh(monkeypatch):
    saved, statuses, sessions, closed = [], [], [], []
    event = threading.Event()

    class Hermes:
        def create_session(self, cwd):
            session = str(len(sessions))
            sessions.append(session)
            return session

        def stream_prompt(self, session, prompt, **kwargs):
            try:
                yield "first"
                yield "late"
            finally:
                closed.append(session)

    monkeypatch.setattr(ai_service, "get_hermes_connection", lambda: Hermes())
    monkeypatch.setattr(ai_service, "_build_conversation_messages", lambda: [])
    monkeypatch.setattr(ai_service, "add_message", lambda *args, **kwargs: saved.append(args))
    monkeypatch.setattr(ai_service, "update_status", statuses.append)
    stream = ai_service.stream_ai_response("old", cancellation_event=event)
    assert next(stream) == "first"
    event.set()
    with pytest.raises(OperationCancelled):
        next(stream)
    assert saved == [("user", "old")]
    assert statuses == ["thinking"]
    assert closed == ["0"]
    assert list(ai_service.stream_ai_response("new", cancellation_event=threading.Event())) == ["first", "late"]
    assert sessions == ["0", "1"]
    assert saved[-1] == ("assistant", "firstlate")
    assert statuses[-1] == "listening"
    assert list(ai_service.stream_ai_response("again", cancellation_event=threading.Event())) == ["first", "late"]
    assert sessions == ["0", "1"]  # Successful interruptible turns reuse session 1.


def test_precancelled_stream_does_not_start_provider(monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(ai_service, "add_message", lambda *a, **k: pytest.fail("Must not start"))
    with pytest.raises(OperationCancelled):
        list(ai_service.stream_ai_response("hello", cancellation_event=event))


def test_acp_local_wait_cancels_without_claiming_remote_request_stopped(monkeypatch):
    connection = HermesACPConnection(executable="unused")
    started, release, worker_done, consumer_done = [threading.Event() for _ in range(4)]
    cancellation = threading.Event()
    errors = []

    def request(*args, **kwargs):
        started.set()
        try:
            assert release.wait(2)
        finally:
            worker_done.set()

    monkeypatch.setattr(connection, "_send_request", request)

    def consume():
        try:
            list(connection.stream_prompt("session", "hello", cancellation_event=cancellation))
        except OperationCancelled as exc:
            errors.append(exc)
        finally:
            consumer_done.set()

    thread = threading.Thread(target=consume)
    thread.start()
    try:
        assert started.wait(1)
        cancellation.set()
        assert consumer_done.wait(1)
        assert len(errors) == 1
        assert not worker_done.is_set()  # Only local consumption was stopped.
        assert connection._notification_handlers == []
    finally:
        release.set()
        thread.join(2)
        assert worker_done.wait(1)


def test_permission_denial_still_returns_cancelled_outcome(monkeypatch):
    connection = HermesACPConnection(executable="unused")
    sent = []
    monkeypatch.setattr(connection, "_write_jsonrpc", sent.append)
    connection._handle_server_request({"id": "permission", "method": "session/request_permission"})
    assert sent[0]["result"] == {"outcome": {"outcome": "cancelled"}}


def test_late_cancelled_session_notifications_cannot_contaminate_next_turn(monkeypatch):
    connection = HermesACPConnection(executable="unused")
    sessions, saved = [], []
    release, old_done = threading.Event(), threading.Event()

    def create_session(cwd):
        session = str(len(sessions))
        sessions.append(session)
        return session

    def emit(session, text):
        connection._handle_message({
            "method": "session/update",
            "params": {"sessionId": session, "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            }},
        })

    def request(method, params, **kwargs):
        session = params["sessionId"]
        if session == "0":
            emit(session, "partial")
            try:
                assert release.wait(3)
            finally:
                old_done.set()
        else:
            assert not old_done.is_set()
            emit("0", "OLD OUTPUT MUST NOT LEAK")
            emit(session, "new answer")
        return {"stopReason": "end_turn"}

    monkeypatch.setattr(connection, "create_session", create_session)
    monkeypatch.setattr(connection, "_send_request", request)
    monkeypatch.setattr(ai_service, "get_hermes_connection", lambda: connection)
    monkeypatch.setattr(ai_service, "_build_conversation_messages", lambda: [])
    monkeypatch.setattr(ai_service, "update_status", lambda status: None)
    monkeypatch.setattr(ai_service, "add_message", lambda *a, **k: saved.append(a))
    cancellation = threading.Event()
    old = ai_service.stream_ai_response("old", cancellation_event=cancellation)
    try:
        assert next(old) == "partial"
        cancellation.set()
        with pytest.raises(OperationCancelled):
            next(old)
        assert connection._notification_handlers == []
        assert list(ai_service.stream_ai_response("new", cancellation_event=threading.Event())) == ["new answer"]
        assert list(ai_service.stream_ai_response("again", cancellation_event=threading.Event())) == ["new answer"]
        assert sessions == ["0", "1"]
        assert connection._notification_handlers == []
        assert [item for item in saved if item[0] == "assistant"] == [
            ("assistant", "new answer"), ("assistant", "new answer"),
        ]
    finally:
        release.set()
        old.close()
        assert old_done.wait(1)


@pytest.mark.parametrize("abandon", ["close", "error", "overlap"])
def test_unfinished_sessions_are_not_reused(monkeypatch, abandon):
    sessions = []

    class Hermes:
        def create_session(self, cwd):
            session = str(len(sessions))
            sessions.append(session)
            return session

        def stream_prompt(self, session, prompt, **kwargs):
            yield "first"
            if abandon == "error" and session == "0":
                raise RuntimeError("transport failed")

    monkeypatch.setattr(ai_service, "get_hermes_connection", lambda: Hermes())
    monkeypatch.setattr(ai_service, "_build_conversation_messages", lambda: [])
    monkeypatch.setattr(ai_service, "update_status", lambda status: None)
    monkeypatch.setattr(ai_service, "add_message", lambda *a, **k: None)
    old = ai_service.stream_ai_response("old", cancellation_event=threading.Event())
    assert next(old) == "first"
    try:
        if abandon == "close":
            old.close()
        elif abandon == "error":
            with pytest.raises(RuntimeError, match="transport failed"):
                next(old)
        assert list(ai_service.stream_ai_response("new", cancellation_event=threading.Event())) == ["first"]
        assert sessions == ["0", "1"]
    finally:
        old.close()


def test_router_passes_controller_signal_and_producer_exits(monkeypatch):
    controller = ConversationInterruptController(Speech())
    started, stopped = threading.Event(), threading.Event()

    def stream(command, cancellation_event):
        assert cancellation_event is controller.interrupted
        started.set()
        try:
            assert cancellation_event.wait(1)
            check_cancelled(cancellation_event)
            yield "must not be emitted"
        finally:
            stopped.set()

    monkeypatch.setattr(router, "stream_ai_response", stream)
    result = []
    consumer = threading.Thread(target=lambda: result.extend(router._stream_with_interrupt("hello", controller)))
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
