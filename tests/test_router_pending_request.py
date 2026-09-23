from pathlib import Path

import pytest

from commands import actions, router
from models.tool_request import ToolRequest
from services.capability_executor import CapabilityExecutionResult
from services import conversation_manager as conversation


@pytest.fixture(autouse=True)
def isolate_conversation_state():
    conversation.clear_pending_request()
    conversation.clear_topic()
    yield
    conversation.clear_pending_request()
    conversation.clear_topic()


@pytest.mark.parametrize("candidates,response,expected", [
    ([], "router.py", "router.py"),
    ([], "router", "router"),
    ([], "tool manager", "tool manager"),
    ([Path("services/tool_manager.py"), Path("commands/router.py")],
     "tool manager.py", "tool_manager.py"),
])
def test_filename_reply_completes_pending_request_without_ai(
    monkeypatch, candidates, response, expected,
):
    executed = []
    monkeypatch.setattr(actions, "speak", lambda text: None)
    monkeypatch.setattr(actions, "find_matching_files", lambda filename: candidates)

    def unexpected(*args, **kwargs):
        pytest.fail("Filename clarification should not require AI")

    def execute(request):
        assert not conversation.has_pending_request()
        executed.append(request)

    monkeypatch.setattr(router, "execute_tool", execute)
    monkeypatch.setattr(router, "detect_tool", unexpected)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "stream_ai_response", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    conversation.clear_pending_request()
    try:
        actions.explain_file_action("tool" if candidates else None)
        assert conversation.has_pending_request()
        router.process(response)
        assert len(executed) == 1
        assert executed[0].tool == "explain_file"
        assert executed[0].arguments == {"filename": expected}
    finally:
        conversation.clear_pending_request()


@pytest.mark.parametrize("candidates", [None, [Path("router.py")]])
def test_new_time_command_clears_pending_and_uses_registered_capability(
    monkeypatch, candidates,
):
    request = ToolRequest("explain_file")
    conversation.set_pending_request({
        "request": request, "missing": "filename", "candidates": candidates,
    })
    executed = []

    def execute(capability_name, arguments=None):
        assert not conversation.has_pending_request()
        executed.append(capability_name)
        return CapabilityExecutionResult(
            success=True, capability=capability_name,
            data={"response": "The current time is 9:00 AM"},
        )

    def unexpected(*args, **kwargs):
        pytest.fail("A new time command must use its deterministic capability")

    monkeypatch.setattr(router, "execute_capability", execute)
    monkeypatch.setattr(router, "execute_tool", unexpected)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    monkeypatch.setattr(router, "speak", lambda text: None)
    router.process("what time is it?")
    assert executed == ["current_time"]
    assert request.arguments == {}
    assert not conversation.has_pending_request()

    # The abandoned clarification must not consume a later conversational turn.
    heard = []
    monkeypatch.setattr(router, "ask_ai", lambda text: heard.append(text))
    router.process("router.py", allow_interruption=False)
    assert heard == ["router.py"]


@pytest.mark.parametrize("command,tool,arguments", [
    ("summarize actions.py", "summarize_file", {"filename": "actions.py"}),
    ("what about actions.py", "explain_file", {"filename": "actions.py", "depth": 1}),
    ("tell me more", "explain_file", {"filename": "topic.py", "depth": 2}),
])
def test_deterministic_intent_supersedes_pending_filename(
    monkeypatch, command, tool, arguments,
):
    original = ToolRequest("explain_file")
    conversation.set_pending_request({
        "request": original, "missing": "filename", "candidates": None,
    })
    conversation.set_topic({"type": "file", "filename": "topic.py"})
    executed = []

    def execute(request):
        assert not conversation.has_pending_request()
        executed.append(request)

    def unexpected(*args, **kwargs):
        pytest.fail("Recognized intent should follow its deterministic route")

    monkeypatch.setattr(router, "execute_tool", execute)
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    router.process(command)
    assert executed == [ToolRequest(tool, arguments)]
    assert original.arguments == {}
    assert not conversation.has_pending_request()


@pytest.mark.parametrize("missing,response", [
    ("filename", "unknown.py"),
    ("filename", "router"),
    ("date", "tomorrow"),
])
def test_unresolved_pending_request_reprompts_without_execution_or_ai(
    monkeypatch, missing, response,
):
    spoken = []
    request = ToolRequest("explain_file")
    pending = {
        "request": request,
        "missing": missing,
        "candidates": [Path("router.py"), Path("test_router.py")],
        "prompt": "Please clarify.",
    }

    def unexpected(*args, **kwargs):
        pytest.fail("Unresolved pending request must not execute or guess via AI")

    monkeypatch.setattr(router, "speak", spoken.append)
    monkeypatch.setattr(router, "execute_tool", unexpected)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    conversation.set_pending_request(pending)
    try:
        router.process(response)
        assert spoken == ["Please clarify."]
        assert conversation.get_pending_request() is pending
        assert request.arguments == {}
    finally:
        conversation.clear_pending_request()
