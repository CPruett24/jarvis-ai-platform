from services.agent_response_service import (
    process_agent_response,
)


def test_preserves_raw_agent_response():

    raw = (
        "# Research\n\n"
        "Artificial intelligence is growing.[1]\n\n"
        "## Sources\n"
        "[1] https://example.com"
    )

    result = process_agent_response(
        raw
    )

    assert (
        result.raw_response
        == raw
    )


def test_creates_clean_speech_response():

    raw = (
        "# Research\n\n"
        "Artificial intelligence is growing.[1]\n\n"
        "## Sources\n"
        "[1] https://example.com"
    )

    result = process_agent_response(
        raw
    )

    assert (
        "Artificial intelligence is growing."
        in result.speech_response
    )

    assert "#" not in (
        result.speech_response
    )

    assert "[1]" not in (
        result.speech_response
    )

    assert "https://" not in (
        result.speech_response
    )


def test_empty_response():

    result = process_agent_response(
        ""
    )

    assert result.raw_response == ""

    assert result.speech_response == ""