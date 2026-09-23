import pytest

from services.capability_request import (
    normalize_request,
    detect_capability_request,
    detect_capability_management_request,
)


@pytest.mark.parametrize("command", [
    "what is a calendar", "how does email work", "what is an event loop",
    "is email encryption secure", "tell me about email encryption",
    "what is a code review", "explain how to browse the web",
    "my calendar design uses a grid", "explain what capabilities are available means",
])
def test_subject_mentions_do_not_select_capabilities(command):
    assert not detect_capability_request(command).matched
    assert not detect_capability_management_request(command).matched


def test_unregistered_capability_is_not_claimed(monkeypatch):
    from services import capability_request
    monkeypatch.setattr(capability_request, "get_capability", lambda name: None)
    assert not detect_capability_request("check my calendar").matched
    assert not detect_capability_management_request("do I have calendar access").matched


def test_normalize_request():

    assert (
        normalize_request(
            "  What's on my Calendar?! "
        )
        == "what's on my calendar"
    )


def test_detect_calendar_request():

    result = detect_capability_request(
        "What's on my calendar?"
    )

    assert result.matched is True
    assert result.capability_name == "calendar"
    assert result.confidence == 1.0


def test_detect_schedule_request():

    result = detect_capability_request(
        "What do I have scheduled today?"
    )

    assert result.matched is True
    assert result.capability_name == "calendar"


def test_detect_email_request():

    result = detect_capability_request(
        "Check my email"
    )

    assert result.matched is True
    assert result.capability_name == "email"


def test_detect_code_review_request():

    result = detect_capability_request(
        "Can you review my code?"
    )

    assert result.matched is True
    assert result.capability_name == "code_review"


def test_detect_multi_file_request():

    result = detect_capability_request(
        "How do these files work together?"
    )

    assert result.matched is True
    assert result.capability_name == (
        "multi_file_reasoning"
    )


def test_normal_conversation_is_not_capability_request():

    result = detect_capability_request(
        "What do you think about Python?"
    )

    assert result.matched is False


def test_empty_request():

    result = detect_capability_request("")

    assert result.matched is False

@pytest.mark.parametrize(
    "command",
    [
        "browse the web",
        "browse the internet",
        "open a website",
        "go to a website",
        "use the browser",
    ],
)
def test_explicit_browser_control_selects_browser_capability(
    command,
):
    result = detect_capability_request(command)

    assert result.matched
    assert result.capability_name == "browser_automation"


@pytest.mark.parametrize(
    "command",
    [
        "browse the web for Python 3.13 changes",
        "browse the internet for Python 3.13 changes",
    ],
)
def test_browser_research_does_not_select_browser_capability(
    command,
):
    result = detect_capability_request(command)

    assert not result.matched