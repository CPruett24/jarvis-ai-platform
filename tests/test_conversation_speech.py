import time
import threading
import pytest

from services.conversation_speech import (
    ConversationSpeech,
)


def test_complete_sentence_is_queued():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    result = speech.add_chunk(
        "Hello from JARVIS."
    )

    speech.wait_until_finished()

    assert result == [
        "Hello from JARVIS."
    ]

    assert spoken == [
        "Hello from JARVIS."
    ]

    speech.stop()


def test_partial_sentence_is_not_spoken():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    result = speech.add_chunk(
        "Hello from "
    )

    speech.wait_until_finished()

    assert result == []

    assert spoken == []

    speech.stop()


def test_sentence_is_spoken_when_completed():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    speech.add_chunk(
        "Hello from "
    )

    result = speech.add_chunk(
        "JARVIS."
    )

    speech.wait_until_finished()

    assert result == [
        "Hello from JARVIS."
    ]

    assert spoken == [
        "Hello from JARVIS."
    ]

    speech.stop()


def test_multiple_sentences_are_queued():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    result = speech.add_chunk(
        "Hello. How are you?"
    )

    speech.wait_until_finished()

    assert result == [
        "Hello.",
        "How are you?",
    ]

    assert spoken == [
        "Hello.",
        "How are you?",
    ]

    speech.stop()


def test_finish_queues_remaining_text():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    speech.add_chunk(
        "This response has no punctuation"
    )

    assert spoken == []

    result = speech.finish()

    speech.wait_until_finished()

    assert result == [
        "This response has no punctuation"
    ]

    assert spoken == [
        "This response has no punctuation"
    ]

    speech.stop()


def test_finish_does_not_duplicate_sentences():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    speech.add_chunk(
        "Hello."
    )

    speech.wait_until_finished()

    result = speech.finish()

    speech.wait_until_finished()

    assert result == []

    assert spoken == [
        "Hello."
    ]

    speech.stop()


def test_speech_queue_does_not_block_streaming():

    spoken = []

    def slow_speak(text):

        time.sleep(
            0.2
        )

        spoken.append(
            text
        )

    speech = ConversationSpeech(
        speak_function=slow_speak
    )

    start = time.perf_counter()

    speech.add_chunk(
        "First sentence."
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    assert elapsed < 0.1

    speech.wait_until_finished()

    assert spoken == [
        "First sentence."
    ]

    speech.stop()


def test_sentences_are_spoken_in_order():

    spoken = []

    speech = ConversationSpeech(
        speak_function=spoken.append
    )

    speech.add_chunk(
        "First."
    )

    speech.add_chunk(
        "Second."
    )

    speech.add_chunk(
        "Third."
    )

    speech.wait_until_finished()

    assert spoken == [
        "First.",
        "Second.",
        "Third.",
    ]

    speech.stop()

def test_interrupt_stops_current_speech(
    monkeypatch,
):

    spoken = []

    stopped = []

    def fake_speak(text):

        spoken.append(text)

    def fake_stop_speaking():

        stopped.append(True)

    monkeypatch.setattr(
        "services.conversation_speech.stop_speaking",
        fake_stop_speaking,
    )

    speech = ConversationSpeech(
        speak_function=fake_speak,
    )

    speech.add_chunk(
        "This is the first sentence."
    )

    speech.interrupt()

    assert stopped == [True]


@pytest.mark.parametrize("attempt", range(10))
def test_interrupt_discards_queued_sentences(
    monkeypatch, attempt,
):
    spoken = []
    worker_entered, release_worker = threading.Event(), threading.Event()
    original_worker = ConversationSpeech._speech_worker

    def gated_worker(self):
        worker_entered.set()
        assert release_worker.wait(2), "Test did not release its worker"
        original_worker(self)

    monkeypatch.setattr(ConversationSpeech, "_speech_worker", gated_worker)
    stopped = threading.Event()
    speech = ConversationSpeech(speak_function=spoken.append, stop_function=stopped.set)
    try:
        assert worker_entered.wait(1)
        speech.add_chunk("First sentence. Second sentence.")
        speech.interrupt()
        assert stopped.wait(1)
        assert speech.speech_queue.unfinished_tasks == 0
        release_worker.set()
        assert speech.wait_until_finished(1)
        assert spoken == []  # Both utterances were definitely queued at cancellation.
    finally:
        release_worker.set()
        assert speech.stop()


@pytest.mark.parametrize("attempt", range(10))
def test_interrupt_discards_waiting_sentences_after_playback_started(attempt):
    spoken = []
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()

    def blocking_speak(text):
        spoken.append(text)
        entered.set()
        assert release.wait(2)

    def stop():
        stopped.set()
        release.set()

    speech = ConversationSpeech(speak_function=blocking_speak, stop_function=stop)
    try:
        speech.add_chunk("Active sentence.")
        assert entered.wait(1)
        speech.add_chunk("Waiting sentence. Another waiting sentence.")
        speech.interrupt()
        assert stopped.wait(1)
        assert speech.wait_until_finished(1)
        assert spoken == ["Active sentence."]
        assert speech.last_success_at is None
        assert speech.playback_outcome().value == "interrupted"
    finally:
        release.set()
        assert speech.stop()


def test_reset_allows_speech_after_interrupt(
):

    spoken = []

    def fake_speak(text):

        spoken.append(text)

    speech = ConversationSpeech(
        speak_function=fake_speak,
    )

    speech.interrupt()

    speech.reset()

    speech.add_chunk(
        "New response."
    )

    speech.wait_until_finished()

    assert spoken == [
        "New response."
    ]

def test_interrupt_monitor_calls_callback(
    monkeypatch,
):

    captured = {}

    def fake_transcribe(audio, **kwargs):
        return "stop jarvis"

    def fake_callback(text):
        captured["text"] = text

    monkeypatch.setattr(
        "services.listener.transcribe_audio",
        fake_transcribe,
    )

    from services.listener import (
        SpeechInterruptMonitor,
    )

    monitor = SpeechInterruptMonitor(
        fake_callback,
    )

    # The microphone callback should only process
    # audio while the interrupt monitor is running.
    monitor.running = True

    monitor._callback(
        None,
        object(),
    )

    assert captured["text"] == (
        "stop jarvis"
    )


def test_interrupt_monitor_ignores_empty_transcription(
    monkeypatch,
):

    called = []

    def fake_transcribe(audio, **kwargs):
        return ""

    def fake_callback(text):
        called.append(text)

    monkeypatch.setattr(
        "services.listener.transcribe_audio",
        fake_transcribe,
    )

    from services.listener import (
        SpeechInterruptMonitor,
    )

    monitor = SpeechInterruptMonitor(
    fake_callback,
    )

    monitor.running = True

    monitor._callback(
        None,
        object(),
    )

    assert called == []

def test_interrupt_stops_current_speech_and_clears_queue():

    spoken = []
    stopped = []

    def fake_speak(text):
        spoken.append(text)

    def fake_stop():
        stopped.append(True)

    speech = ConversationSpeech(
        speak_function=fake_speak,
        stop_function=fake_stop,
    )

    speech.add_chunk(
        "This is the first sentence. "
    )

    speech.add_chunk(
        "This is the second sentence. "
    )

    speech.interrupt()

    assert stopped == [True]
    assert speech.interrupted.is_set()


def test_interrupted_conversation_does_not_queue_new_sentences():

    spoken = []
    stopped = []

    def fake_speak(text):
        spoken.append(text)

    def fake_stop():
        stopped.append(True)

    speech = ConversationSpeech(
        speak_function=fake_speak,
        stop_function=fake_stop,
    )

    speech.interrupt()

    result = speech.add_chunk(
        "This should not be spoken."
    )

    assert result == []
    assert spoken == []
    assert stopped == [True]
