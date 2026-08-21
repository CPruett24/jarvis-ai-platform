from services.capability_executor import (
    CapabilityExecutionResult,
)


def format_capability_result(
    result: CapabilityExecutionResult,
):
    """
    Convert a capability execution result into a natural
    response that JARVIS can speak to the user.
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

    return (
        f"The {result.capability} capability "
        "completed successfully."
    )