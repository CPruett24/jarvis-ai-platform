import time

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