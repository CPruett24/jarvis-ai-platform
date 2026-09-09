from services.agent_response_service import (
    process_agent_response,
)

from services.agent_response_service import (
    process_agent_response,
    get_agent_result_information,
)

from services.agents.base_agent import (
    AgentExecutionResult,
)

from models.information import (
    InformationSource,
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

def test_successful_agent_result_creates_agent_result_information():

    result = AgentExecutionResult(
        success=True,
        agent="hermes",
        message="The project contains 12 Python files.",
    )

    information = get_agent_result_information(
        result
    )

    assert len(information) == 1

    item = information[0]

    assert item.content == (
        "The project contains 12 Python files."
    )

    assert item.source == (
        InformationSource.AGENT_RESULT
    )


def test_failed_agent_result_creates_no_information():

    result = AgentExecutionResult(
        success=False,
        agent="hermes",
        error="Permission denied.",
    )

    information = get_agent_result_information(
        result
    )

    assert information == []


def test_empty_agent_result_creates_no_information():

    result = AgentExecutionResult(
        success=True,
        agent="hermes",
        message="",
    )

    information = get_agent_result_information(
        result
    )

    assert information == []