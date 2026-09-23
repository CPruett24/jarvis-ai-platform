from pathlib import Path

import pytest

from models.tool_request import ToolRequest
from services.conversation_manager import (
    has_pending_request,
    set_topic,
    get_topic,
    clear_topic,
    is_follow_up,
    is_topic_switch,
    resolve_follow_up,
    resolve_topic_switch,
    record_turn,
    get_conversation_context,
    clear_context,
    set_pending_request,
    get_pending_request,
    clear_pending_request,
    complete_pending_request,
)


@pytest.fixture(autouse=True)
def isolate_topic():
    clear_topic()
    yield
    clear_topic()


def test_topic_snapshots_and_default_depth():
    original = {"type": "file", "filename": "router.py"}
    set_topic(original)
    assert "depth" not in original
    original["filename"] = "changed.py"
    snapshot = get_topic()
    assert snapshot == {"type": "file", "filename": "router.py", "depth": 1}
    snapshot["filename"] = "also_changed.py"
    get_conversation_context()["topic"]["depth"] = 99
    assert get_topic()["filename"] == "router.py"
    assert get_topic()["depth"] == 1
    clear_topic()
    assert get_topic() is None
    assert get_conversation_context()["topic"] is None


@pytest.mark.parametrize("invalid", [
    {}, {"type": ""}, {"type": "file"},
    {"type": "file", "filename": " "},
    *[{"type": "file", "filename": "router.py", "depth": depth}
      for depth in [0, -1, True, "2", None]],
])
def test_invalid_topic_does_not_replace_committed_topic(invalid):
    set_topic({"type": "file", "filename": "router.py"})
    before = get_topic()
    with pytest.raises(ValueError):
        set_topic(invalid)
    assert get_topic() == before


@pytest.mark.parametrize("phrase", [
    "tell me more", "explain that", "explain it", "why", "how so", "go on", "continue",
])
def test_follow_up_proposes_depth_without_committing(phrase):
    set_topic({"type": "file", "filename": "router.py"})
    for _ in range(2):
        request = resolve_follow_up(phrase.upper() + "?")
        assert request.arguments == {"filename": "router.py", "depth": 2}
        assert get_topic()["depth"] == 1
    set_topic({"type": "file", **request.arguments})
    assert resolve_follow_up(phrase).arguments["depth"] == 3


def test_no_topic_unsupported_topic_and_unrelated_follow_up():
    assert resolve_follow_up("continue") is None
    set_topic({"type": "unsupported"})
    assert resolve_follow_up("continue") is None
    set_topic({"type": "file", "filename": "router.py"})
    assert resolve_follow_up("hello") is None
    assert get_topic()["depth"] == 1


@pytest.mark.parametrize("text", ["whynot", "continue_work", "go onward", "explain itself"])
def test_follow_up_requires_phrase_boundary(text):
    assert not is_follow_up(text)


@pytest.mark.parametrize("phrase", [
    "what about", "how about", "what's in", "now explain", "next explain", "next",
])
def test_topic_switch_proposes_target_without_changing_topic(phrase):
    set_topic({"type": "file", "filename": "old.py", "depth": 3})
    request = resolve_topic_switch(phrase + " router.py")
    assert request.arguments == {"filename": "router.py", "depth": 1}
    assert get_topic() == {"type": "file", "filename": "old.py", "depth": 3}
    assert resolve_topic_switch(phrase) is None


def test_topic_switch_requires_phrase_boundary():
    assert not is_topic_switch("nextdoor.py")
    assert resolve_topic_switch("nextdoor.py") is None

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
        response="router.py"
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


@pytest.mark.parametrize("response", ["tool manager.py", "TOOL_MANAGER.PY", "manager"])
def test_pending_filename_resolves_normalized_candidate(response):
    request = ToolRequest("explain_file", {"depth": 2})
    set_pending_request({
        "request": request,
        "missing": "filename",
        "candidates": [Path("services/tool_manager.py"), Path("commands/router.py")],
    })
    try:
        assert complete_pending_request(response) is request
        assert request.arguments == {"depth": 2, "filename": "tool_manager.py"}
        assert get_pending_request() is None
        assert get_conversation_context()["pending_request"] is None
        assert complete_pending_request(response) is None
    finally:
        clear_pending_request()


@pytest.mark.parametrize("missing,response,candidates", [
    ("date", "tomorrow", None),
    ("filename", None, None),
    ("filename", "   ", None),
    ("filename", 123, None),
    ("filename", "what time is it", None),
    ("filename", "how are you", None),
    ("filename", "tell me about this computer", None),
    ("filename", "router?", None),
    ("filename", "missing.py", [Path("router.py")]),
    ("filename", ".py", [Path("router.py")]),
    ("filename", "router", [Path("router.py"), Path("test_router.py")]),
    ("filename", "router.py", [Path("a/router.py"), Path("b/router.py")]),
])
def test_unresolved_pending_request_is_unchanged(missing, response, candidates):
    request = ToolRequest("explain_file", {"depth": 2})
    pending = {
        "request": request,
        "missing": missing,
        "candidates": candidates,
        "prompt": "Please clarify.",
    }
    set_pending_request(pending)
    try:
        assert complete_pending_request(response) is None
        assert get_pending_request() is pending
        assert request.arguments == {"depth": 2}
        assert get_conversation_context()["pending_request"] == pending
    finally:
        clear_pending_request()


def test_pending_filename_can_be_completed_without_candidates_key():
    request = ToolRequest("explain_file")
    set_pending_request({"request": request, "missing": "filename"})
    try:
        assert complete_pending_request(" router.py ") is request
        assert request.arguments == {"filename": "router.py"}
        assert not has_pending_request()
    finally:
        clear_pending_request()
