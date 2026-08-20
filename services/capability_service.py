from dataclasses import dataclass

from commands.static_commands import COMMANDS
from commands.tool_manager import get_tool

from services.capability_registry import (
    get_capability as get_registered_capability_from_registry,
    get_available_capabilities,
    get_unavailable_capabilities,
    get_capability_status,
)


@dataclass
class Capability:
    """
    Describes a capability known to JARVIS.
    """

    name: str

    description: str

    tool_name: str | None = None

    registered: bool = True

    available: bool = True

    enabled: bool = True

    requires_confirmation: bool = False

    requires_authentication: bool = False


@dataclass
class CapabilityMatch:
    """
    Describes a capability JARVIS can use for a request.
    """

    available: bool

    tool_name: str | None = None

    description: str | None = None

    source: str = "none"

    capability: Capability | None = None

def get_capability(name):
    """
    Return an executable tool-backed capability by name.

    This preserves the existing capability-service API.
    """

    if not name:
        return None

    for capability in get_registered_capabilities():

        if capability.name == name:
            return capability

    return None

def normalize_command(command):
    """
    Normalize a command for deterministic capability matching.
    """

    if not command:
        return ""

    return " ".join(
        command.lower().strip().split()
    ).strip(".,!? ")


def _get_available_tools():
    """
    Import the tool registry lazily to avoid unnecessary
    import coupling during module initialization.
    """

    from commands.tool_manager import get_available_tools

    return get_available_tools()


def get_registered_capabilities():
    """
    Return all capabilities currently registered with JARVIS.

    Tool-backed capabilities are available when their
    underlying tool exists.
    """

    capabilities = []

    for tool_name, tool in _get_available_tools().items():

        capabilities.append(
            Capability(
                name=tool_name,
                description=tool.get(
                    "description",
                    "No description available.",
                ),
                tool_name=tool_name,
                registered=True,
                available=True,
                enabled=True,
            )
        )

    return capabilities

def resolve_capability(command):
    """
    Determine whether JARVIS has a deterministic capability
    for the supplied command.

    AI interpretation should not be introduced here.
    """

    normalized = normalize_command(command)

    if not normalized:
        return CapabilityMatch(
            available=False
        )

    tool_name = COMMANDS.get(
        normalized
    )

    if not tool_name:
        return CapabilityMatch(
            available=False
        )

    tool = get_tool(
        tool_name
    )

    if tool is None:
        return CapabilityMatch(
            available=False
        )

    capability = Capability(
        name=tool_name,
        description=tool.get(
            "description",
            "No description available.",
        ),
        tool_name=tool_name,
        registered=True,
        available=True,
        enabled=True,
    )

    return CapabilityMatch(
        available=(
            capability.registered
            and capability.available
            and capability.enabled
        ),
        tool_name=tool_name,
        description=capability.description,
        source="static_command",
        capability=capability,
    )


def get_capability_context():
    """
    Build capability information for the AI.

    The AI is told the difference between capabilities that
    exist and capabilities that are currently usable.
    """

    capabilities = get_registered_capabilities()

    if not capabilities:
        return "No capabilities are currently registered."

    lines = [
        "JARVIS capability registry:"
    ]

    for capability in capabilities:

        status = "available"

        if not capability.enabled:
            status = "disabled"

        elif not capability.available:
            status = "unavailable"

        requirements = []

        if capability.requires_authentication:
            requirements.append(
                "authentication required"
            )

        if capability.requires_confirmation:
            requirements.append(
                "user confirmation required"
            )

        requirement_text = ""

        if requirements:
            requirement_text = (
                " ("
                + ", ".join(requirements)
                + ")"
            )

        lines.append(
            f"- {capability.name}: "
            f"{capability.description} "
            f"[{status}{requirement_text}]"
        )

    lines.append("")
    lines.append("Capability rules:")
    lines.append(
        "- Registered means JARVIS knows the capability exists."
    )
    lines.append(
        "- Available means JARVIS can currently use the capability."
    )
    lines.append(
        "- Disabled means the capability is intentionally turned off."
    )
    lines.append(
        "- Never claim an unavailable or disabled capability was executed."
    )
    lines.append(
        "- Never claim access to an external system unless a capability actually provides that access."
    )
    lines.append(
        "- If a requested capability is unavailable, say so clearly."
    )

    return "\n".join(lines)

def get_registered_capability(name):
    """
    Return a capability from the high-level capability registry.

    This includes capabilities that are registered but not
    currently available for execution.
    """

    return get_registered_capability_from_registry(
        name
    )


def get_available_capability_list():
    """
    Return names of capabilities currently available.
    """

    return list(
        get_available_capabilities().keys()
    )


def get_unavailable_capability_list():
    """
    Return names of capabilities that are registered
    but not currently available.
    """

    return list(
        get_unavailable_capabilities().keys()
    )

def explain_capability_availability(name):
    """
    Generate a concise user-facing explanation of whether
    a registered capability is currently available.
    """

    capability = (
        get_registered_capability(
            name
        )
    )

    if capability is None:

        return (
            "I don't currently have that capability "
            "registered."
        )

    if capability.available:

        return (
            f"{capability.name} is currently available."
        )

    reason = capability.reason

    if reason:

        return (
            f"I have a {capability.name.lower()} "
            f"capability planned, but I can't use it yet. "
            f"{reason}"
        )

    return (
        f"I know about the {capability.name.lower()} "
        "capability, but it isn't currently available."
    )