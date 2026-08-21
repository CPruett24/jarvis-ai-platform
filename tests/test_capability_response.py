from services.capability_executor import (
    CapabilityExecutionResult,
)

from services.capability_response import (
    format_capability_result,
)


def test_successful_result_uses_message():

    result = CapabilityExecutionResult(
        success=True,
        capability="current_time",
        message="The current time is 7:00 PM.",
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "The current time is 7:00 PM."
    )


def test_successful_result_without_message():

    result = CapabilityExecutionResult(
        success=True,
        capability="test_capability",
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "The test_capability capability "
        "completed successfully."
    )


def test_failed_result_uses_error():

    result = CapabilityExecutionResult(
        success=False,
        capability="calendar",
        error=(
            "Calendar integration has not "
            "been configured yet."
        ),
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "I couldn't complete the calendar "
        "capability. Calendar integration has "
        "not been configured yet."
    )


def test_failed_result_without_error():

    result = CapabilityExecutionResult(
        success=False,
        capability="calendar",
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "I couldn't complete the calendar "
        "capability."
    )