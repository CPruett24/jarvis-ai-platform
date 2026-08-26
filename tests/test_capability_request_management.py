from services.capability_request import (
    detect_capability_management_request,
)


def test_detect_list_capabilities():

    result = detect_capability_management_request(
        "What can you do?"
    )

    assert result.matched is True
    assert result.action == "list"
    assert result.confidence == 1.0


def test_detect_what_capabilities_do_you_have():

    result = detect_capability_management_request(
        "What capabilities do you have?"
    )

    assert result.matched is True
    assert result.action == "list"


def test_detect_disabled_capabilities():

    result = detect_capability_management_request(
        "What capabilities are disabled?"
    )

    assert result.matched is True
    assert result.action == "list_disabled"


def test_detect_unavailable_capabilities():

    result = detect_capability_management_request(
        "Which capabilities are unavailable?"
    )

    assert result.matched is True
    assert result.action == "list_unavailable"


def test_detect_capability_status():

    result = detect_capability_management_request(
        "What's the status of my capabilities?"
    )

    assert result.matched is True
    assert result.action == "status"


def test_normal_conversation_is_not_management_request():

    result = detect_capability_management_request(
        "I need help deciding what to work on."
    )

    assert result.matched is False
    assert result.action == ""


def test_empty_request_is_not_management_request():

    result = detect_capability_management_request(
        ""
    )

    assert result.matched is False

def test_detect_calendar_details():

    result = detect_capability_management_request(
        "Is calendar available?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == "calendar"
    assert result.confidence == 1.0


def test_detect_calendar_unavailable_reason():

    result = detect_capability_management_request(
        "Why can't you use my calendar?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == "calendar"


def test_detect_browser_details():

    result = detect_capability_management_request(
        "Can you use browser automation?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == (
        "browser_automation"
    )


def test_detect_email_details():

    result = detect_capability_management_request(
        "Why can't you use my email?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == "email"


def test_details_unknown_capability_is_not_matched():

    result = detect_capability_management_request(
        "Is quantum computer control available?"
    )

    assert result.matched is False

def test_detect_current_time_details():

    result = detect_capability_management_request(
        "Is current time available?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == "current_time"
    assert result.confidence == 1.0

def test_detect_hermes_details():

    result = detect_capability_management_request(
        "Is Hermes available?"
    )

    assert result.matched is True
    assert result.action == "details"
    assert result.capability_name == "hermes_agent"
    assert result.confidence == 1.0