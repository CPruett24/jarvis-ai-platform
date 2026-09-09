from dataclasses import dataclass

from services.agent_response_formatter import (
    clean_agent_response,
)

from services.grounding_service import (
    create_agent_result_information,
)


@dataclass(frozen=True)
class AgentResponse:
    """
    Represents an external agent response in both its
    original form and a speech-friendly form.
    """

    raw_response: str

    speech_response: str


def process_agent_response(
    response,
    max_speech_length=1200,
):
    """
    Preserve the original external agent response while
    creating a cleaned version suitable for JARVIS to speak.
    """

    raw_response = (
        str(response)
        if response
        else ""
    )

    speech_response = clean_agent_response(
        raw_response,
        max_length=max_speech_length,
    )

    return AgentResponse(
        raw_response=raw_response,
        speech_response=speech_response,
    )


def get_agent_result_information(result):
    """
    Convert a successful external agent result into
    explicitly marked agent-produced information.

    Agent results are not treated as deterministic
    observations.
    """

    if not result.success:
        return []

    if not result.message:
        return []

    return [
        create_agent_result_information(
            result.message
        )
    ]