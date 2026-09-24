from services.sentence_buffer import (
    SentenceBuffer,
)


def test_emits_complete_sentence():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Hello from JARVIS."
    ) == [
        "Hello from JARVIS."
    ]


def test_waits_for_sentence_boundary():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Hello from "
    ) == []

    assert buffer.add(
        "JARVIS."
    ) == [
        "Hello from JARVIS."
    ]


def test_handles_multiple_sentences():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Hello. How are you?"
    ) == [
        "Hello.",
        "How are you?",
    ]


def test_handles_sentences_across_chunks():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Hello. How "
    ) == [
        "Hello."
    ]

    assert buffer.add(
        "are you today?"
    ) == [
        "How are you today?"
    ]


def test_handles_exclamation_marks():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Excellent!"
    ) == [
        "Excellent!"
    ]


def test_handles_question_marks():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Are you ready?"
    ) == [
        "Are you ready?"
    ]


def test_flush_returns_remaining_text():

    buffer = SentenceBuffer()

    assert buffer.add(
        "This sentence has no punctuation"
    ) == []

    assert buffer.flush() == [
        "This sentence has no punctuation"
    ]


def test_flush_clears_buffer():

    buffer = SentenceBuffer()

    buffer.add(
        "Some unfinished text"
    )

    assert buffer.flush() == [
        "Some unfinished text"
    ]

    assert buffer.flush() == []


def test_empty_chunks_are_ignored():

    buffer = SentenceBuffer()

    assert buffer.add("") == []

    assert buffer.flush() == []


def test_sentence_boundary_requires_whitespace():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Version 2.0"
    ) == []

    assert buffer.add(
        " is ready."
    ) == [
        "Version 2.0 is ready."
    ]

def test_emits_long_phrase_at_comma():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Python is commonly used for web development, "
        "automation and data analysis."
    ) == [
        "Python is commonly used for web development,",
        "automation and data analysis.",
    ]

    assert buffer.flush() == []


def test_short_comma_does_not_emit():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Yes, that is correct."
    ) == [
        "Yes, that is correct."
    ]


def test_emits_long_phrase_at_semicolon():

    buffer = SentenceBuffer()

    assert buffer.add(
        "The project has finished loading successfully; "
        "everything is ready."
    ) == [
        "The project has finished loading successfully;",
        "everything is ready.",
    ]

    assert buffer.flush() == []

def test_emits_long_phrase_at_colon():

    buffer = SentenceBuffer()

    assert buffer.add(
        "There is one important thing you should know: "
        "the server is offline."
    ) == [
        "There is one important thing you should know:",
        "the server is offline.",
    ]

    assert buffer.flush() == []


def test_decimal_does_not_split_sentence():

    buffer = SentenceBuffer()

    assert buffer.add(
        "The value is 3.14 and everything is normal."
    ) == [
        "The value is 3.14 and everything is normal."
    ]


def test_version_number_does_not_split():

    buffer = SentenceBuffer()

    assert buffer.add(
        "Python 3.12 is installed and ready."
    ) == [
        "Python 3.12 is installed and ready."
    ]
