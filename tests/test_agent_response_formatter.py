from services.agent_response_formatter import (
    clean_agent_response,
)


def test_removes_markdown():

    response = clean_agent_response(
        "## Hello\n\n**This is important.**"
    )

    assert response == (
        "Hello This is important."
    )


def test_removes_citations():

    response = clean_agent_response(
        "Artificial intelligence is growing.[1][2]"
    )

    assert response == (
        "Artificial intelligence is growing."
    )


def test_removes_urls():

    response = clean_agent_response(
        "More information: https://example.com/test"
    )

    assert response == (
        "More information:"
    )


def test_removes_sources_section():

    response = clean_agent_response(
        "Research completed.\n\n"
        "## Sources\n\n"
        "[1] https://example.com"
    )

    assert response == (
        "Research completed."
    )


def test_truncates_long_response():

    text = (
        "This is sentence one. "
        "This is sentence two. "
        "This is sentence three."
    )

    response = clean_agent_response(
        text,
        max_length=40,
    )

    assert len(response) <= 40


def test_empty_response():

    assert clean_agent_response(
        ""
    ) == ""