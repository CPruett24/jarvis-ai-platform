"""Controlled lifecycle regressions; run with run_voice_regressions.py."""
import io
import json
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from commands import router
from services import listener, conversation_lifecycle, conversation_service
from services.conversation_interrupt import ConversationInterruptController
from services.conversation_speech import ConversationSpeech
from services.speaker import InterruptibleSpeaker
from services.tts.local_provider import LocalTTSProvider
from services.tts import local_worker
from services.tts.fallback_provider import FallbackTTSProvider


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(conversation_service, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(router, "speak", lambda *a: None)
    monkeypatch.setattr(router, "stop_speaking", lambda: None)
    monkeypatch.setattr(router, "process_dynamic_command", lambda *a: False)
    monkeypatch.setattr("services.speaker.update_status", lambda *a: None)
    monkeypatch.setattr("services.speaker.update_last_response", lambda *a: None)
    conversation_lifecycle.reset_active_conversation()
    yield
    conversation_lifecycle.reset_active_conversation()


@pytest.mark.parametrize("utterances,selected", [
    (["You", "How does inheritance work?"], "How does inheritance work?"),
    (["You", "That's all"], "That's all"),
    (["You", "How does inheritance work?", "encoding"], "How does inheritance work?"),
    (["You", "question", "That's all", "another question"], "That's all"),
    (["stop"], "stop"), (["wait"], "wait"),
])
def test_bounded_handoff(utterances, selected):
    controller = ConversationInterruptController(SimpleNamespace(interrupt=lambda: pytest.fail("callback stopped TTS")))
    for utterance in utterances:
        controller.handle_speech(utterance)
    assert controller.was_interrupted()
    assert controller.state == "cancelling"
    assert controller.handoff() == selected
    controller.handle_speech("stale")
    assert controller.get_interrupted_text() == selected
    assert controller.state == "handed_off"


@pytest.mark.parametrize("last,expected", [("question", "question"), ("That's all", "That's all")])
def test_router_seals_after_monitor_drain(monkeypatch, last, expected):
    events = []

    class Monitor:
        def __init__(self, callback):
            self.callback = callback

        def start(self):
            self.callback("You")

        def stop(self):
            self.callback(last)
            events.append("monitor_closed")

    class Speech:
        def start_response(self):
            pass

        def interrupt(self):
            events.append("cancel")

        def stop(self):
            events.append("disposed")

    monkeypatch.setattr(router, "SpeechInterruptMonitor", Monitor)
    monkeypatch.setattr(router, "ConversationSpeech", Speech)
    monkeypatch.setattr(router, "stream_ai_response", lambda *a, **k: iter([]))
    assert router.process_streaming_conversation("question") == router.INTERRUPTION_PREFIX + expected
    assert events.count("cancel") == 1
    assert events[-2:] == ["disposed", "monitor_closed"]


def test_nested_questions_keep_barge_in_and_end_result(monkeypatch):
    seen = []
    results = iter([router.INTERRUPTION_PREFIX + "how does inheritance work?",
                    router.INTERRUPTION_PREFIX + "That's all"])

    def stream(command):
        seen.append(command)
        return next(results)

    monkeypatch.setattr(router, "process_streaming_conversation", stream)
    monkeypatch.setattr(router, "ask_ai", lambda *a: pytest.fail("Barge-in disabled"))
    assert router.process("what is REST?") is conversation_lifecycle.CONVERSATION_ENDED
    assert seen == ["what is rest", "how does inheritance work"]


def test_many_handoffs_do_not_grow_router_stack(monkeypatch):
    count = 0

    def stream(command):
        nonlocal count
        count += 1
        return router.INTERRUPTION_PREFIX + ("that's all" if count == 1100 else "what is REST?")

    monkeypatch.setattr(router, "process_streaming_conversation", stream)
    assert router.process("what is REST?") is conversation_lifecycle.CONVERSATION_ENDED
    assert count == 1100


def test_local_worker_engine_operations_have_one_owner(monkeypatch):
    calls = []
    owner = threading.get_ident()

    def record(name):
        calls.append((name, threading.get_ident()))

    engine = SimpleNamespace(say=lambda text: record("say"),
                             runAndWait=lambda: record("play"), stop=lambda: record("stop"))
    monkeypatch.setitem(sys.modules, "pyttsx3", SimpleNamespace(init=lambda: record("init") or engine))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps("Hello")))
    local_worker.main()
    assert calls == [(name, owner) for name in ["init", "say", "play", "stop"]]


def sleeping_child(*args, **kwargs):
    # Exercise real process termination without loading pyttsx3 or audio APIs.
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)


def test_local_cancellation_reaps_blocked_child_and_recovers():
    created = threading.Event()
    children = []

    def factory(*args, **kwargs):
        child = sleeping_child(**kwargs)
        children.append(child)
        created.set()
        return child

    provider = LocalTTSProvider(factory)
    for _ in range(3):
        created.clear()
        worker = threading.Thread(target=provider.speak, args=("Hello",), daemon=True)
        worker.start()
        try:
            assert created.wait(2)
            start = time.monotonic()
            stops = [threading.Thread(target=provider.stop) for _ in range(8)]
            for stop in stops:
                stop.start()
            for stop in stops:
                stop.join(0.5)
                assert not stop.is_alive()
            assert time.monotonic() - start < 1
            worker.join(2)
            assert not worker.is_alive()
            assert children[-1].poll() is not None
        finally:
            provider.stop()
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=1)
            worker.join(2)


def test_local_cancellation_during_launch_and_before_playback():
    launching, release = threading.Event(), threading.Event()
    child = SimpleNamespace(returncode=0, stdin=io.StringIO(),
                            poll=lambda: 0, communicate=lambda **k: pytest.fail("Cancelled playback"))

    def factory(*a, **k):
        launching.set()
        assert release.wait(1)
        return child

    provider = LocalTTSProvider(factory)
    worker = threading.Thread(target=provider.speak, args=("Hello",), daemon=True)
    worker.start()
    try:
        assert launching.wait(1)
        provider.stop()
    finally:
        release.set()
        worker.join(1)
    assert not worker.is_alive()
    provider.speak_cancellable("Hello", cancelled_event())
    provider.stop()  # After completion is harmless.


def cancelled_event():
    event = threading.Event()
    event.set()
    return event


def test_fallback_transition_preserves_operation_cancellation():
    event = threading.Event()
    calls = []

    def primary(text):
        event.set()
        raise RuntimeError("Primary failed during cancellation")

    provider = FallbackTTSProvider(SimpleNamespace(speak=primary, stop=lambda: None),
                                   SimpleNamespace(speak=calls.append, stop=lambda: None))
    provider.speak_cancellable("hello", event)
    assert not calls


def test_blocked_stop_and_playback_have_bounded_resource_ownership():
    playing, stopping, release = threading.Event(), threading.Event(), threading.Event()

    def play(text):
        playing.set()
        release.wait(3)

    def stop():
        stopping.set()
        release.wait(3)

    speaker = InterruptibleSpeaker(SimpleNamespace(speak=play, stop=stop))
    speech = ConversationSpeech(speak_function=speaker.speak, stop_function=speaker.stop)
    try:
        speech.add_chunk("First sentence.")
        assert playing.wait(1)
        start = time.monotonic()
        speech.interrupt()
        assert stopping.wait(1)
        for _ in range(20):
            speaker.stop()
            speech.interrupt()
        assert not speech.stop(timeout=0.02)
        assert time.monotonic() - start < 1
        stop_worker = speaker.stop_worker
        # Subsequent responses do not create new blocked provider operations.
        for _ in range(5):
            following = ConversationSpeech(speak_function=speaker.speak, stop_function=speaker.stop)
            following.add_chunk("Following sentence.")
            assert following.wait_until_finished(timeout=0.5)
            assert following.stop()
        assert speaker.stop_worker is stop_worker
    finally:
        release.set()
        speech.worker.join(1)
        if speaker.stop_worker:
            speaker.stop_worker.join(1)
    assert not speech.worker.is_alive()


def test_repeated_successful_turns_dispose_workers(monkeypatch):
    workers = []

    def make_speech():
        speech = ConversationSpeech(speak_function=lambda text: None, stop_function=lambda: None)
        workers.append(speech.worker)
        return speech

    monkeypatch.setattr(router, "ConversationSpeech", make_speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda callback: SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(router, "stream_ai_response", lambda *a, **k: iter(["Hello."]))
    for _ in range(15):
        assert router.process_streaming_conversation("hello") == "Hello."
    assert all(not worker.is_alive() for worker in workers)


def test_monitor_shutdown_bounds_decoder_and_suppresses_late_callback(monkeypatch):
    decoding, release, source_closed = threading.Event(), threading.Event(), threading.Event()
    captured = []

    class Microphone:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            source_closed.set()

    def transcribe(audio, **kwargs):
        assert source_closed.is_set()
        decoding.set()
        assert release.wait(2)
        return "That's all"

    monkeypatch.setattr(listener, "create_microphone", Microphone)
    monkeypatch.setattr(listener.recognizer, "listen", lambda *a, **k: object())
    monkeypatch.setattr(listener, "transcribe_audio", transcribe)
    monitor = listener.SpeechInterruptMonitor(captured.append)
    monitor.start()
    try:
        assert decoding.wait(1)
        assert not monitor.stop(timeout=0.02)
        following = listener.SpeechInterruptMonitor(captured.append)
        following.start()
        assert following.thread is None  # No accumulation of stuck decoders.
        assert listener.capture_lock.acquire(timeout=0.1)
        listener.capture_lock.release()
    finally:
        release.set()
        monitor.thread.join(1)
    assert not monitor.thread.is_alive()
    assert captured == []


def test_monitor_drains_already_captured_end_control(monkeypatch):
    decoding, release = threading.Event(), threading.Event()
    captured = []
    monkeypatch.setattr(listener, "create_microphone", lambda: object())

    def transcribe(audio, **kwargs):
        decoding.set()
        assert release.wait(1)
        return "That's all"

    monkeypatch.setattr(listener, "transcribe_audio", transcribe)
    monitor = listener.SpeechInterruptMonitor(captured.append)
    monitor.running = True
    monitor.thread = threading.Thread(target=monitor._callback, args=(None, object()), daemon=True)
    monitor.thread.start()
    assert decoding.wait(1)
    release.set()
    assert monitor.stop(timeout=1)
    assert captured == ["That's all"]


def test_blocked_ai_producer_does_not_accumulate_or_block_router(monkeypatch):
    started, release, done = threading.Event(), threading.Event(), threading.Event()

    def blocked_stream(*args, **kwargs):
        started.set()
        try:
            assert release.wait(2)
            yield "late"
        finally:
            done.set()

    monkeypatch.setattr(router, "stream_ai_response", blocked_stream)
    controller = ConversationInterruptController(None)
    consumer = threading.Thread(target=lambda: list(router._stream_with_interrupt("first", controller)), daemon=True)
    consumer.start()
    try:
        assert started.wait(1)
        controller.handle_speech("stop")
        consumer.join(0.5)
        assert not consumer.is_alive()
        for _ in range(5):
            following = list(router._stream_with_interrupt("next", ConversationInterruptController(None)))
            assert following == ["The previous AI response is still cancelling. Please try again shortly."]
    finally:
        release.set()
        consumer.join(1)
        assert done.wait(1)
        # The producer releases its slot immediately after the generator closes.
        assert router._conversation_producer_slot.acquire(timeout=1)
        router._conversation_producer_slot.release()


def test_stream_watchdog_returns_control_and_cleans_workers(monkeypatch):
    release, started, done = threading.Event(), threading.Event(), threading.Event()
    workers = []

    def stream(*args, **kwargs):
        started.set()
        try:
            assert release.wait(2)
            yield "late"
        finally:
            done.set()

    def speech():
        result = ConversationSpeech(speak_function=lambda text: None, stop_function=lambda: None)
        workers.append(result.worker)
        return result

    monkeypatch.setattr(router, "MAX_VOICE_RESPONSE_SECONDS", 0.03)
    monkeypatch.setattr(router, "stream_ai_response", stream)
    monkeypatch.setattr(router, "ConversationSpeech", speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: SimpleNamespace(start=lambda: None, stop=lambda: None))
    try:
        assert router.process_streaming_conversation("question") == ""
        assert started.is_set()
        assert all(not worker.is_alive() for worker in workers)
    finally:
        release.set()
        assert done.wait(1)
        assert router._conversation_producer_slot.acquire(timeout=1)
        router._conversation_producer_slot.release()


def test_playback_watchdog_returns_control(monkeypatch):
    events = []
    speech = SimpleNamespace(start_response=lambda: None, add_chunk=lambda text: None,
                             finish=lambda: None, is_finished=lambda: False,
                             interrupt=lambda: events.append("cancel"), stop=lambda: events.append("disposed"))
    monkeypatch.setattr(router, "MAX_VOICE_RESPONSE_SECONDS", 0.03)
    monkeypatch.setattr(router, "PLAYBACK_INACTIVITY_SECONDS", 0.03)
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: SimpleNamespace(start=lambda: None, stop=lambda: events.append("monitor_closed")))
    monkeypatch.setattr(router, "stream_ai_response", lambda *a, **k: iter(["answer"]))
    assert router.process_streaming_conversation("question") == "answer"
    assert events == ["cancel", "disposed", "monitor_closed"]


def test_local_kill_escalation_is_bounded_and_refuses_overlapping_child():
    calls = []

    class Unreapable:
        returncode = None

        def poll(self):
            return None

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("fake-child", timeout)

        def terminate(self):
            calls.append("terminate")

        def kill(self):
            calls.append("kill")

    provider = LocalTTSProvider(lambda *a, **k: Unreapable())
    provider.MAX_UTTERANCE_SECONDS = 0
    provider.speak("hello")
    assert calls == ["terminate", "kill"]
    with pytest.raises(RuntimeError, match="recovering"):
        provider.speak("next")


def test_monitor_initialization_failure_still_disposes_speech(monkeypatch):
    workers = []

    def speech():
        result = ConversationSpeech(speak_function=lambda text: None, stop_function=lambda: None)
        workers.append(result.worker)
        return result

    def failed_monitor(callback):
        raise RuntimeError("Input unavailable")

    monkeypatch.setattr(router, "ConversationSpeech", speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", failed_monitor)
    with pytest.raises(RuntimeError, match="Input unavailable"):
        router.process_streaming_conversation("question")
    assert all(not worker.is_alive() for worker in workers)
