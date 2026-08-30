from dataclasses import dataclass, field

from services.capability_registry import get_capability
from services.capability_state import (
    is_capability_enabled_for,
)
from commands.tool_manager import get_tool
from models.tool_request import ToolRequest

from services.grounding_service import (
    create_observed_information,
)

@dataclass
class CapabilityExecutionResult:
    """
    Structured result from executing a JARVIS capability.
    """

    success: bool
    capability: str
    message: str = ""
    data: dict = field(default_factory=dict)
    error: str | None = None

def get_observed_information(
    result,
):

    if not result.success:

        return []

    information = []

    if result.message:

        information.append(
            create_observed_information(
                result.message
            )
        )

    for key, value in result.data.items():

        information.append(
            create_observed_information(
                f"{key}: {value}"
            )
        )

    return information

def execute_capability(
    capability_name,
    arguments=None,
):
    """
    Execute an available registered capability.

    This layer sits between the capability registry,
    capability state manager, and existing tool manager.
    """

    capability = get_capability(
        capability_name
    )

    if capability is None:

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error="Capability is not registered.",
        )

    if not capability.available:

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error=(
                capability.reason
                or "Capability is not currently available."
            ),
        )

    if not is_capability_enabled_for(
        capability_name,
        capability,
    ):

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error="Capability is currently disabled.",
        )

    if not capability.tool_name:

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error="Capability has no executable tool.",
        )

    tool = get_tool(
        capability.tool_name
    )

    if tool is None:

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error=(
                "Capability is marked available, "
                "but its tool is not registered."
            ),
        )

    request = ToolRequest(
        tool=capability.tool_name,
        arguments=arguments or {},
    )

    try:

        function = tool["function"]

        result = function(
            **request.arguments
        )

        if isinstance(result, dict):

            data = result

        else:

            data = {
                "result": result
            }

        return CapabilityExecutionResult(
            success=True,
            capability=capability_name,
            message=(
                f"{capability.name} executed successfully."
            ),
            data=data,
        )

    except Exception as exc:

        return CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error=str(exc),
        )