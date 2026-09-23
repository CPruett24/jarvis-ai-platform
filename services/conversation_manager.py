import re

from enum import Enum
from models.tool_request import ToolRequest
from dataclasses import dataclass
from enum import Enum

from models.tool_request import ToolRequest

FOLLOW_UP_PHRASES = {
    "tell me more",
    "explain that",
    "explain it",
    "why",
    "how so",
    "go on",
    "continue",
}

SWITCH_TOPIC_PHRASES = {
    "what about",
    "how about",
    "what's in",
    "now explain",
    "next explain",
    "next",
}

@dataclass
class PendingRequest:
    request: ToolRequest
    missing: str
    candidates: list | None = None
    prompt: str = ""

class ConversationMode(Enum):
    CHAT = "chat"
    TOOL = "tool"
    CLARIFICATION = "clarification"


_current_topic = None
_pending_request = None

_recent_turns = []

MAX_CONTEXT_TURNS = 6


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


def clear_topic():

    global _current_topic

    _current_topic = None


def record_turn(role, content):

    global _recent_turns

    _recent_turns.append(
        {
            "role": role,
            "content": content,
        }
    )

    if len(_recent_turns) > MAX_CONTEXT_TURNS:
        _recent_turns = _recent_turns[-MAX_CONTEXT_TURNS:]


def get_recent_turns():

    return list(_recent_turns)


def clear_context():

    global _recent_turns

    _recent_turns = []


def get_conversation_context():

    topic = get_topic()
    pending = get_pending_request()

    return {
        "topic": topic.copy() if topic else None,
        "pending_request": pending.copy() if pending else None,
        "recent_turns": get_recent_turns(),
    }


def is_follow_up(command):

    command = command.lower().strip()

    return any(
        command.startswith(phrase)
        for phrase in FOLLOW_UP_PHRASES
    )


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


def _resolve_pending_filename(response, candidates):

    if not isinstance(response, str) or not response.strip():
        return None

    filename = response.strip()

    if not candidates:
        # Accept short filename/path fragments, not arbitrary sentences or questions.
        if not re.fullmatch(r"[\w./\\:-]+(?: +[\w./\\:-]+){0,2}", filename):
            return None
        if filename.lower().split()[0] in {
            "what", "what's", "when", "where", "who", "which", "why", "how",
            "can", "could", "would", "should", "is", "are", "do", "does", "did",
        }:
            return None
        return filename

    query = filename.lower().replace("_", "").replace(" ", "").replace(".py", "")

    if not query:
        return None

    matches = [
        path for path in candidates
        if query in path.stem.lower().replace("_", "").replace(" ", "")
    ]

    if len(matches) == 1:
        return matches[0].name

    return None


def complete_pending_request(response=None):
    """Resolve the missing field; retain pending state on unsupported/invalid input."""

    pending = get_pending_request()

    if pending is None:
        return None

    missing = pending["missing"]

    if missing == "filename":
        value = _resolve_pending_filename(response, pending.get("candidates"))
    else:
        return None

    if value is None:
        return None

    request = pending["request"]
    request.arguments[missing] = value

    clear_pending_request()

    return request


def is_topic_switch(command):

    command = command.lower().strip()

    return any(
        command.startswith(phrase)
        for phrase in SWITCH_TOPIC_PHRASES
    )


def resolve_topic_switch(command):

    text = command.lower().strip()

    for phrase in SWITCH_TOPIC_PHRASES:

        if text.startswith(phrase):

            filename = text[len(phrase):].strip()

            if not filename:
                return None

            return ToolRequest(
                tool="explain_file",
                arguments={
                    "filename": filename,
                    "depth": 1,
                }
            )

    return None
