from services.capability_service import (
    Capability,
    normalize_command,
    resolve_capability,
    get_capability,
    get_registered_capabilities,
)

from services.capability_service import (
    get_registered_capability,
    get_available_capability_list,
    get_unavailable_capability_list,
)

from services.capability_service import (
    explain_capability_availability,
)


def test_normalize_command():

    assert (
        normalize_command(
            "  What time is it?! "
        )
        == "what time is it"
    )


def test_resolve_current_time():

    result = resolve_capability(
        "what time is it"
    )

    assert result.available is True
    assert result.tool_name == "current_time"
    assert result.source == "static_command"

    assert result.capability is not None
    assert result.capability.name == "current_time"
    assert result.capability.enabled is True
    assert result.capability.available is True


def test_resolve_git_status():

    result = resolve_capability(
        "git status"
    )

    assert result.available is True
    assert result.tool_name == "git_status"


def test_unknown_capability():

    result = resolve_capability(
        "what is on my calendar"
    )

    assert result.available is False
    assert result.tool_name is None
    assert result.capability is None


def test_empty_command():

    result = resolve_capability("")

    assert result.available is False


def test_get_registered_capabilities():

    capabilities = (
        get_registered_capabilities()
    )

    assert capabilities

    names = [
        capability.name
        for capability in capabilities
    ]

    assert "current_time" in names
    assert "git_status" in names


def test_get_capability():

    capability = get_capability(
        "current_time"
    )

    assert capability is not None
    assert isinstance(
        capability,
        Capability,
    )

    assert capability.name == "current_time"
    assert capability.tool_name == "current_time"
    assert capability.enabled is True
    assert capability.available is True


def test_unknown_capability_name():

    capability = get_capability(
        "calendar"
    )

    assert capability is None

def test_capability_is_registered():

    capability = get_capability(
        "current_time"
    )

    assert capability is not None
    assert capability.registered is True


def test_available_capability_is_enabled():

    capability = get_capability(
        "current_time"
    )

    assert capability is not None
    assert capability.available is True
    assert capability.enabled is True


def test_capability_match_requires_registered_available_enabled():

    result = resolve_capability(
        "what time is it"
    )

    assert result.capability is not None

    assert result.capability.registered is True
    assert result.capability.available is True
    assert result.capability.enabled is True

    assert result.available is True

def test_registered_calendar_capability():

    capability = get_registered_capability(
        "calendar"
    )

    assert capability is not None
    assert capability.available is False


def test_available_capability_list():

    capabilities = get_available_capability_list()

    assert "current_time" in capabilities


def test_unavailable_capability_list():

    capabilities = get_unavailable_capability_list()

    assert "calendar" in capabilities

def test_explain_unavailable_calendar():

    response = (
        explain_capability_availability(
            "calendar"
        )
    )

    assert "calendar" in response.lower()
    assert "can't use it yet" in response.lower()


def test_explain_available_capability():

    response = (
        explain_capability_availability(
            "current_time"
        )
    )

    assert "available" in response.lower()