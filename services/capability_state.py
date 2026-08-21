from dataclasses import dataclass

from services.capability_registry import (
    get_capability,
)


@dataclass(frozen=True)
class CapabilityState:
    """
    Represents the current operational state of a JARVIS
    capability.
    """

    name: str
    registered: bool
    available: bool
    enabled: bool


# Runtime enable/disable state.

_DISABLED_CAPABILITIES = set()


def get_capability_state(
    capability_name,
):
    """
    Return the current state of a registered capability.

    Unknown capabilities return None.
    """

    capability = get_capability(
        capability_name
    )

    if capability is None:
        return None

    enabled = (
        capability.available
        and capability_name
        not in _DISABLED_CAPABILITIES
    )

    return CapabilityState(
        name=capability_name,
        registered=True,
        available=capability.available,
        enabled=enabled,
    )


def is_capability_enabled(
    capability_name,
):
    """
    Return whether a capability is currently enabled.
    """

    state = get_capability_state(
        capability_name
    )

    if state is None:
        return False

    return (
        state.registered
        and state.available
        and state.enabled
    )


def is_capability_available(
    capability_name,
):
    """
    Return whether a capability can currently be used.
    """

    return is_capability_enabled(
        capability_name
    )


def enable_capability(
    capability_name,
):
    """
    Enable an available capability.

    Unavailable capabilities cannot be enabled.
    Unknown capabilities return False.
    """

    capability = get_capability(
        capability_name
    )

    if capability is None:
        return False

    if not capability.available:
        return False

    _DISABLED_CAPABILITIES.discard(
        capability_name
    )

    return True


def disable_capability(
    capability_name,
):
    """
    Disable a registered capability.

    Unknown capabilities return False.
    """

    capability = get_capability(
        capability_name
    )

    if capability is None:
        return False

    _DISABLED_CAPABILITIES.add(
        capability_name
    )

    return True

def is_capability_enabled_for(
    capability_name,
    capability,
):
    """
    Determine whether a resolved capability object is enabled.

    This supports both registry-backed capabilities and
    locally supplied/test capability objects.
    """

    if capability is None:
        return False

    if not capability.available:
        return False

    if capability_name in _DISABLED_CAPABILITIES:
        return False

    return True