from models.intent import Intent
from models.tool_request import ToolRequest

from commands.static_commands import COMMANDS

from services.code_intent import (
    is_code_question,
    is_contextual_code_question,
)

from services.conversation_manager import (
    get_topic,
    is_follow_up,
    is_topic_switch,
)

from services.command_parser import parse_command


def resolve_intent(command):

    command = command.lower().strip()

    topic = get_topic()

    # ---------------------------------------------------------
    # Code conversation
    #
    # Code intent must be checked before generic follow-ups.
    #
    # Example:
    # "why is aliases here"
    #
    # "why" is technically a follow-up phrase, but the active
    # topic tells us this is a question about the current code.
    # ---------------------------------------------------------

    if topic and (
        is_code_question(command)
        or is_contextual_code_question(command)
    ):

        return Intent(
            type="code_question",
            confidence=0.95,
            metadata={
                "topic": topic,
            },
        )

    # ---------------------------------------------------------
    # Follow-up conversation
    # ---------------------------------------------------------

    if topic and is_follow_up(command):

        return Intent(
            type="follow_up",
            confidence=1.0,
            metadata={
                "topic": topic,
            },
        )

    # ---------------------------------------------------------
    # Topic switch
    # ---------------------------------------------------------

    if is_topic_switch(command):

        return Intent(
            type="topic_switch",
            confidence=1.0,
            metadata={
                "topic": topic,
            },
        )

    # ---------------------------------------------------------
    # Explicitly parsed tool command
    # ---------------------------------------------------------

    parsed = parse_command(command)

    if parsed:

        return Intent(
            type="tool",
            confidence=1.0,
            tool_request=parsed,
        )

    # ---------------------------------------------------------
    # Static command registry
    #
    # This mirrors the existing router behavior.
    # ---------------------------------------------------------

    if command in COMMANDS:

        return Intent(
            type="tool",
            confidence=1.0,
            tool_request=ToolRequest(
                tool=COMMANDS[command]
            ),
        )

    # ---------------------------------------------------------
    # General conversation
    # ---------------------------------------------------------

    return Intent(
        type="conversation",
        confidence=0.5,
    )