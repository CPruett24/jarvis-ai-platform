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
_pending_request = None

def set_pending_request(request):

    global _pending_request

    _pending_request = request


def get_pending_request():

    return _pending_request


def clear_pending_request():

    global _pending_request

    _pending_request = None

def has_pending_request():

    return _pending_request is not None

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

def complete_pending_request(filename=None):

    pending = get_pending_request()

    if pending is None:
        return None

    request = pending["request"]

    if pending["missing"] == "filename":

        if pending["candidates"]:

            query = (
                filename.lower()
                .replace("_", "")
                .replace(" ", "")
                .replace(".py", "")
            )

            for path in pending["candidates"]:

                stem = (
                    path.stem.lower()
                    .replace("_", "")
                    .replace(" ", "")
                )

                if query in stem:

                    filename = path.name

                    break

        request.arguments["filename"] = filename

    clear_pending_request()

    return request