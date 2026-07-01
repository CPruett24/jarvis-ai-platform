from enum import Enum
from models.tool_request import ToolRequest

FOLLOW_UP_PHRASES = {
    "what about",
    "tell me more",
    "explain that",
    "explain it",
    "why",
    "how so",
    "go on",
    "continue",
}

class ConversationMode(Enum):
    CHAT = "chat"
    TOOL = "tool"
    CLARIFICATION = "clarification"


_current_topic = None


def set_topic(topic):

    global _current_topic

    if "depth" not in topic:
        topic["depth"] = 1

    _current_topic = topic


def get_topic():
    return _current_topic

def is_follow_up(command):

    command = command.lower().strip()

    result = any(
        command.startswith(phrase)
        for phrase in FOLLOW_UP_PHRASES
    )

    return result

def clear_topic():
    global _current_topic
    _current_topic = None


def determine_mode(command, tool_request):

    if tool_request.tool != "none":
        return ConversationMode.TOOL

    return ConversationMode.CHAT

def debug_topic():

    print("\n===== CURRENT TOPIC =====")

    print(_current_topic)

    print("=========================\n")

def resolve_follow_up(command):

    global _current_topic

    topic = get_topic()

    if topic is None:
        return None

    if topic["type"] == "file":

        topic["depth"] += 1

        return ToolRequest(
            tool="explain_file",
            arguments={
                "filename": topic["filename"],
                "depth": topic["depth"],
            }
        )

    return None