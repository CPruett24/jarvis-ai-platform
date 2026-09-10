from models.tool_request import ToolRequest
from services.conversation_manager import (
    has_pending_request,
    set_topic,
    get_topic,
    clear_topic,
    is_follow_up,
    is_topic_switch,
    resolve_follow_up,
    record_turn,
    get_conversation_context,
    clear_context,
    set_pending_request,
    get_pending_request,
    clear_pending_request,
    complete_pending_request,
)

def test_topic_can_be_set_and_retrieved():

    clear_topic()

    set_topic(
        {
            "type": "file",
            "filename": "router.py",
            "depth": 1,
        }
    )

    topic = get_topic()

    assert topic is not None
    assert topic["type"] == "file"
    assert topic["filename"] == "router.py"
    assert topic["depth"] == 1


def test_follow_up_is_detected():

    assert is_follow_up(
        "why is aliases here"
    )

    assert is_follow_up(
        "tell me more"
    )


def test_topic_switch_is_detected():

    assert is_topic_switch(
        "what about tool_manager.py"
    )


def test_follow_up_increases_file_depth():

    set_topic(
        {
            "type": "file",
            "filename": "router.py",
            "depth": 1,
        }
    )

    request = resolve_follow_up(
        "tell me more"
    )

    assert request is not None
    assert request.tool == "explain_file"
    assert request.arguments["filename"] == "router.py"
    assert request.arguments["depth"] == 2

    clear_topic()

def test_conversation_context_contains_topic():

    clear_context()

    set_topic(
        {
            "type": "file",
            "filename": "router.py",
            "depth": 1,
        }
    )

    context = get_conversation_context()

    assert context["topic"] is not None
    assert context["topic"]["filename"] == "router.py"

    clear_topic()
    clear_context()


def test_conversation_context_records_turns():

    clear_context()

    record_turn(
        "user",
        "Why is aliases here?",
    )

    record_turn(
        "assistant",
        "The aliases dictionary normalizes commands.",
    )

    context = get_conversation_context()

    assert len(context["recent_turns"]) == 2

    assert (
        context["recent_turns"][0]["content"]
        == "Why is aliases here?"
    )

    assert (
        context["recent_turns"][1]["content"]
        == "The aliases dictionary normalizes commands."
    )

    clear_context()

def test_pending_request_preserves_prompt():

    clear_pending_request()

    request = ToolRequest(
        tool="explain_file",
        arguments={},
    )

    set_pending_request(
        {
            "request": request,
            "missing": "filename",
            "candidates": None,
            "prompt": (
                "Sure. Which file would you like me to explain?"
            ),
        }
    )

    pending = get_pending_request()

    assert pending is not None
    assert pending["missing"] == "filename"
    assert pending["prompt"] == (
        "Sure. Which file would you like me to explain?"
    )

    clear_pending_request()

def test_pending_request_can_be_completed_with_filename():

    clear_pending_request()

    request = ToolRequest(
        tool="explain_file",
        arguments={},
    )

    set_pending_request(
        {
            "request": request,
            "missing": "filename",
            "candidates": None,
            "prompt": (
                "Sure. Which file would you like me to explain?"
            ),
        }
    )

    completed = complete_pending_request(
        filename="router.py"
    )

    assert completed is not None
    assert completed.tool == "explain_file"
    assert (
        completed.arguments["filename"]
        == "router.py"
    )

    assert not has_pending_request()

def test_conversation_context_contains_pending_request():

    clear_pending_request()

    request = ToolRequest(
        tool="explain_file",
        arguments={},
    )

    set_pending_request(
        {
            "request": request,
            "missing": "filename",
            "candidates": None,
            "prompt": (
                "Sure. Which file would you like me to explain?"
            ),
        }
    )

    context = get_conversation_context()

    assert context["pending_request"] is not None
    assert (
        context["pending_request"]["missing"]
        == "filename"
    )
    assert (
        context["pending_request"]["prompt"]
        == "Sure. Which file would you like me to explain?"
    )

    clear_pending_request()