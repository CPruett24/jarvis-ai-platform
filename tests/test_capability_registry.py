from services.capability_registry import (
    get_capability,
    capability_exists,
    is_capability_available,
    get_available_capabilities,
    get_unavailable_capabilities,
    get_capability_status,
)


def test_current_time_is_available():

    capability = get_capability(
        "current_time"
    )

    assert capability is not None
    assert capability.available is True
    assert capability.tool_name == "current_time"


def test_calendar_is_registered_but_unavailable():

    capability = get_capability(
        "calendar"
    )

    assert capability is not None
    assert capability.available is False
    assert capability.reason is not None


def test_capability_exists():

    assert capability_exists(
        "calendar"
    )

    assert capability_exists(
        "current_time"
    )


def test_unknown_capability_does_not_exist():

    assert not capability_exists(
        "teleportation"
    )


def test_available_capability_check():

    assert is_capability_available(
        "current_time"
    )

    assert not is_capability_available(
        "calendar"
    )


def test_available_capabilities():

    capabilities = get_available_capabilities()

    assert "current_time" in capabilities
    assert "git_status" in capabilities
    assert "calendar" not in capabilities


def test_unavailable_capabilities():

    capabilities = get_unavailable_capabilities()

    assert "calendar" in capabilities
    assert "email" in capabilities
    assert "browser_automation" in capabilities


def test_capability_status_available():

    status = get_capability_status(
        "current_time"
    )

    assert "available" in status.lower()


def test_capability_status_unavailable():

    status = get_capability_status(
        "calendar"
    )

    assert "unavailable" in status.lower()
    assert "calendar integration" in status.lower()


def test_unknown_capability_status():

    status = get_capability_status(
        "does_not_exist"
    )

    assert "not registered" in status.lower()