from services.capability_request import (
    normalize_request,
    detect_capability_request,
)


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