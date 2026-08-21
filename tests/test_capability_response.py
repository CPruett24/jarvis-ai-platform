from services.capability_executor import (
    CapabilityExecutionResult,
)

from services.capability_response import (
    format_capability_result,
)

from services.capability_response_registry import (
    clear_formatters,
)

import pytest


@pytest.fixture(autouse=True)
def reset_formatters():

    clear_formatters()

    yield

    clear_formatters()

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

def test_successful_result_with_structured_data_uses_message():

    result = CapabilityExecutionResult(
        success=True,
        capability="calendar",
        message="You have 1 event today.",
        data={
            "events": [
                {
                    "title": "Team meeting",
                    "time": "2:00 PM",
                }
            ],
            "count": 1,
        },
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "You have 1 event today."
    )


def test_successful_result_with_structured_data_without_message():

    result = CapabilityExecutionResult(
        success=True,
        capability="calendar",
        data={
            "events": [
                {
                    "title": "Team meeting",
                    "time": "2:00 PM",
                }
            ],
            "count": 1,
        },
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "The calendar capability completed successfully."
    )

def test_registered_formatter_can_format_structured_data():

    result = CapabilityExecutionResult(
        success=True,
        capability="test_capability",
        data={
            "name": "Jarvis",
            "count": 3,
        },
    )

    response = format_capability_result(
        result,
        formatters={
            "test_capability": (
                lambda data: (
                    f"{data['name']} has "
                    f"{data['count']} items."
                )
            )
        },
    )

    assert response == (
        "Jarvis has 3 items."
    )


def test_unknown_capability_uses_generic_fallback():

    result = CapabilityExecutionResult(
        success=True,
        capability="unknown_capability",
        data={
            "value": 123,
        },
    )

    response = format_capability_result(
        result,
        formatters={},
    )

    assert response == (
        "The unknown_capability capability "
        "completed successfully."
    )

def test_registered_formatter_is_used_by_default():

    from services.capability_response_registry import (
        register_formatter,
    )

    register_formatter(
        "test_capability",
        lambda data: (
            f"{data['name']} has "
            f"{data['count']} items."
        ),
    )

    result = CapabilityExecutionResult(
        success=True,
        capability="test_capability",
        data={
            "name": "Jarvis",
            "count": 3,
        },
    )

    response = format_capability_result(
        result
    )

    assert response == (
        "Jarvis has 3 items."
    )


def test_explicit_formatter_overrides_registered_formatter():

    result = CapabilityExecutionResult(
        success=True,
        capability="test_capability",
        data={
            "name": "Jarvis",
            "count": 3,
        },
    )

    response = format_capability_result(
        result,
        formatters={
            "test_capability": (
                lambda data: (
                    f"{data['name']} has "
                    f"{data['count']} things."
                )
            )
        },
    )

    assert response == (
        "Jarvis has 3 things."
    )