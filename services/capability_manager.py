from services.capability_registry import (
    CAPABILITY_REGISTRY,
    get_capability,
    get_available_capabilities,
    get_unavailable_capabilities,
)

from services.capability_state import (
    is_capability_enabled,
)


def get_all_capabilities():
    """
    Return all registered capabilities.
    """

    return list(
        CAPABILITY_REGISTRY.values()
    )


def get_available_capability_names():
    """
    Return display names of capabilities that are
    registered, available, and enabled.
    """

    available = []

    for capability_name, capability in (
        get_available_capabilities().items()
    ):

        if is_capability_enabled(
            capability_name
        ):

            available.append(
                capability.name
            )

    return available


def get_disabled_capability_names():
    """
    Return display names of capabilities that are
    currently disabled.
    """

    disabled = []

    for capability_name, capability in (
        CAPABILITY_REGISTRY.items()
    ):

        if not is_capability_enabled(
            capability_name
        ):

            disabled.append(
                capability.name
            )

    return disabled


def get_unavailable_capability_names():
    """
    Return display names of capabilities whose
    integrations are currently unavailable.
    """

    return [
        capability.name
        for capability in (
            get_unavailable_capabilities().values()
        )
    ]


def get_capability_details(
    capability_name,
):
    """
    Return detailed information about a capability.
    """

    capability = get_capability(
        capability_name
    )

    if capability is None:
        return None

    return {
        "name": capability.name,
        "description": capability.description,
        "category": capability.category,
        "available": capability.available,
        "enabled": is_capability_enabled(
            capability_name
        ),
        "tool_name": capability.tool_name,
        "reason": capability.reason,
    }


def get_capability_summary():
    """
    Return a structured summary of the current JARVIS
    capability environment.
    """

    available = []
    unavailable = []
    disabled = []

    for capability_name, capability in (
        CAPABILITY_REGISTRY.items()
    ):

        enabled = is_capability_enabled(
            capability_name
        )

        # An unavailable integration is unavailable
        # regardless of its enabled state.
        if not capability.available:

            unavailable.append(
                capability.name
            )

        elif not enabled:

            disabled.append(
                capability.name
            )

        else:

            available.append(
                capability.name
            )

    return {
        "total": len(
            CAPABILITY_REGISTRY
        ),
        "available": available,
        "unavailable": unavailable,
        "disabled": disabled,
    }