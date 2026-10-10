import re
from typing import NotRequired, TypedDict

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
    "switch to",
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


class ConversationTopic(TypedDict):
    """Committed topic snapshot; file topics require a filename.

    Depth records the last successfully generated file explanation.
    Other topic types can be stored but have no deterministic resolver yet.
    """

    type: str
    depth: int
    filename: NotRequired[str]


_current_topic: ConversationTopic | None = None
_discussion_kind = None
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
    """Validate and copy a topic; callers cannot mutate stored scalar fields."""

    global _current_topic

    topic = dict(topic)
    topic.setdefault("depth", 1)
    if not isinstance(topic.get("type"), str) or not topic["type"].strip():
        raise ValueError("A topic requires a non-empty type.")
    if type(topic["depth"]) is not int or topic["depth"] < 1:
        raise ValueError("Topic depth must be a positive integer.")
    if topic["type"] == "file" and (
        not isinstance(topic.get("filename"), str) or not topic["filename"].strip()
    ):
        raise ValueError("A file topic requires a non-empty filename.")

    _current_topic = topic
    if topic["type"] == "file":
        mark_file_discussion()
    else:
        mark_conversation_discussion()


def mark_file_discussion():
    global _discussion_kind
    _discussion_kind = "file"


def mark_conversation_discussion():
    global _discussion_kind
    _discussion_kind = "conversation"


def is_file_discussion_active():
    return _discussion_kind != "conversation"


def get_topic() -> ConversationTopic | None:
    """Return a snapshot, not the mutable stored topic."""

    return _current_topic.copy() if _current_topic is not None else None


def clear_topic():

    global _current_topic, _discussion_kind

    _current_topic = None
    _discussion_kind = None


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


def _matches_phrase(command, phrase):
    return command == phrase or command.startswith(phrase + " ")


def is_follow_up(command):

    command = command.lower().strip().rstrip(".!?")

    return any(
        _matches_phrase(command, phrase)
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
    """Propose a follow-up without committing depth before execution succeeds."""

    topic = get_topic()

    if topic is None or not is_follow_up(command):
        return None

    from services.code_intent import should_use_file_context

    if topic["type"] == "file" and should_use_file_context(command, topic):

        return ToolRequest(
            tool="explain_file",
            arguments={
                "filename": topic["filename"],
                "depth": topic["depth"] + 1,
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


def is_topic_transition(command):

    command = command.lower().strip().rstrip(".!?")

    return any(
        _matches_phrase(command, phrase)
        for phrase in SWITCH_TOPIC_PHRASES
    )


def is_explicit_file_target(target):
    """Recognize a single filename/path without requiring the file to exist."""
    return bool(re.fullmatch(r"[\w.\-:/\\]+", target) and (
        "/" in target or "\\" in target
        or re.search(r"\.[a-z0-9]+$", target, re.IGNORECASE)
    ))


def is_topic_switch(command):
    return resolve_topic_switch(command) is not None


def resolve_topic_switch(command):
    """Return the eligible file request, or None for a conversational transition."""

    text = command.lower().strip().rstrip(".!?")

    for phrase in sorted(SWITCH_TOPIC_PHRASES, key=lambda phrase: (-len(phrase), phrase)):

        if _matches_phrase(text, phrase):

            filename = text[len(phrase):].strip()

            if not filename:
                return None

            if filename in {"the other file", "other file", "another file", "the next file"}:
                # Let the existing file action request a filename. There is no
                # tracked list/order from which to infer the referenced file.
                return ToolRequest(tool="explain_file", arguments={})

            if not is_explicit_file_target(filename):
                topic = get_topic()
                if not topic or topic.get("type") != "file":
                    return None
                from services.project_service import find_matching_files
                if not find_matching_files(filename):
                    return None

            return ToolRequest(
                tool="explain_file",
                arguments={
                    "filename": filename,
                    "depth": 1,
                }
            )

    return None
