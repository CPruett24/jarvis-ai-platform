from services.capability_executor import (
    CapabilityExecutionResult,
)

from services.capability_response_registry import (
    get_formatter,
)


def format_capability_result(
    result: CapabilityExecutionResult,
    formatters=None,
):
    """
    Convert a capability execution result into a natural
    response that JARVIS can speak to the user.

    Registered capability formatters provide specialized
    formatting for structured capability data.

    An optional formatter mapping can override the registered
    formatters.
    """

    if not result.success:

        if result.error:

            return (
                f"I couldn't complete the "
                f"{result.capability} capability. "
                f"{result.error}"
            )

        return (
            f"I couldn't complete the "
            f"{result.capability} capability."
        )

    if result.message:

        return result.message

    if formatters is not None:

        formatter = formatters.get(
            result.capability
        )

    else:

        formatter = get_formatter(
            result.capability
        )

    if formatter and result.data:

        try:

            return formatter(
                result.data
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):

            pass

    return (
        f"The {result.capability} capability "
        "completed successfully."
    )