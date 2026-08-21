import pytest

from services.capability_state import (
    get_capability_state,
    is_capability_enabled,
    is_capability_available,
    enable_capability,
    disable_capability,
)


def test_registered_available_capability_has_state():

    state = get_capability_state(
        "current_time"
    )

    assert state is not None
    assert state.name == "current_time"
    assert state.registered is True
    assert state.available is True
    assert state.enabled is True


def test_registered_unavailable_capability_has_state():

    state = get_capability_state(
        "calendar"
    )

    assert state is not None
    assert state.registered is True
    assert state.available is False
    assert state.enabled is False


def test_unknown_capability_returns_none():

    state = get_capability_state(
        "does_not_exist"
    )

    assert state is None


def test_available_capability_is_available():

    assert (
        is_capability_available(
            "current_time"
        )
        is True
    )


def test_unavailable_capability_is_not_available():

    assert (
        is_capability_available(
            "calendar"
        )
        is False
    )


def test_available_capability_is_enabled():

    assert (
        is_capability_enabled(
            "current_time"
        )
        is True
    )


def test_disable_capability():

    result = disable_capability(
        "current_time"
    )

    assert result is True

    assert (
        is_capability_enabled(
            "current_time"
        )
        is False
    )


def test_disabled_capability_is_not_available():

    disable_capability(
        "current_time"
    )

    assert (
        is_capability_available(
            "current_time"
        )
        is False
    )


def test_enable_capability():

    disable_capability(
        "current_time"
    )

    result = enable_capability(
        "current_time"
    )

    assert result is True

    assert (
        is_capability_enabled(
            "current_time"
        )
        is True
    )


def test_enable_unavailable_capability_fails():

    result = enable_capability(
        "calendar"
    )

    assert result is False

    assert (
        is_capability_enabled(
            "calendar"
        )
        is False
    )


def test_disable_unknown_capability_fails():

    result = disable_capability(
        "does_not_exist"
    )

    assert result is False


def test_enable_unknown_capability_fails():

    result = enable_capability(
        "does_not_exist"
    )

    assert result is False


@pytest.fixture(autouse=True)
def restore_current_time():

    enable_capability(
        "current_time"
    )

    yield

    enable_capability(
        "current_time"
    )