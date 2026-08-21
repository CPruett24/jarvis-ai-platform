from services.capability_executor import (
    execute_capability,
)

from services.capability_registry import (
    get_capability,
)


def test_execute_current_time():

    result = execute_capability(
        "current_time"
    )

    assert result.success is True
    assert result.capability == "current_time"
    assert result.error is None


def test_unavailable_calendar():

    result = execute_capability(
        "calendar"
    )

    assert result.success is False
    assert result.capability == "calendar"
    assert result.error is not None

def test_unavailable_calendar():

    result = execute_capability(
        "calendar"
    )

    capability = get_capability(
        "calendar"
    )

    assert result.success is False
    assert result.capability == "calendar"
    assert result.error == capability.reason

def test_unknown_capability():

    result = execute_capability(
        "does_not_exist"
    )

    assert result.success is False
    assert result.capability == "does_not_exist"
    assert result.error == (
        "Capability is not registered."
    )


def test_capability_without_tool():

    result = execute_capability(
        "memory"
    )

    assert result.success is False
    assert result.capability == "memory"
    assert result.error is not None