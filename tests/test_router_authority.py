from dataclasses import replace

import pytest

from commands import router, tool_manager
from services import capability_registry, capability_state
from services import conversation_manager as conversation
from services.agents.base_agent import AgentExecutionResult

@pytest.fixture(autouse=True)
def isolated_state():
    conversation.clear_topic()
    conversation.clear_pending_request()
    yield
    conversation.clear_topic()
    conversation.clear_pending_request()


@pytest.mark.parametrize("command,capability", [
    ("what time is it", "current_time"),
    ("what branch am I on", "git_branch"),
    ("what is my git branch", "git_branch"),
    ("show git status", "git_status"),
    ("explain my current git status", "git_status"),
    ("what files are in this project", "project_tree"),
])
@pytest.mark.parametrize("state", ["available", "disabled", "unavailable"])
def test_authoritative_requests_execute_or_report_limitation(monkeypatch, command, capability, state):
    calls, spoken, saved = [], [], []
    registered = capability_registry.CAPABILITY_REGISTRY[capability]
    monkeypatch.setattr(capability_state, "_DISABLED_CAPABILITIES", {capability} if state == "disabled" else set())
    if state == "unavailable":
        monkeypatch.setitem(capability_registry.CAPABILITY_REGISTRY, capability,
                            replace(registered, available=False, reason="Temporarily unavailable."))

    def execute():
        calls.append(capability)
        return {"response": "Verified result.", "observations": {"test_state": "verified"}}

    def unexpected(*args, **kwargs):
        pytest.fail("Authority selection must not use AI or direct tools")

    monkeypatch.setitem(tool_manager.COMMAND_REGISTRY, registered.tool_name, {"function": execute})
    monkeypatch.setattr(router, "execute_tool", unexpected)
    monkeypatch.setattr(router, "detect_tool", unexpected)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    monkeypatch.setattr(router, "speak", spoken.append)
    monkeypatch.setattr(router, "add_message", lambda role, text, source: saved.append((source, text)))
    router.process(command)
    if state == "available":
        assert calls == [capability]
        assert saved == [("observed", "[observed] test_state: verified")]
    else:
        assert not calls
        assert not saved
        assert state in spoken[0].lower()


@pytest.mark.parametrize("topic", [False, True])
@pytest.mark.parametrize("command", [
    "what is a git branch", "explain git status", "explain what git status does",
    "what is a calendar", "how does email work", "what is a coding workspace",
    "can you explain git status",
])
def test_conceptual_questions_remain_conversational_even_with_file_topic(monkeypatch, command, topic):
    if topic:
        conversation.set_topic({"type": "file", "filename": "router.py"})
    heard = []
    def unexpected(*args, **kwargs):
        pytest.fail("Conceptual question must not execute tools or create observations")
    monkeypatch.setattr(router, "execute_capability", unexpected)
    monkeypatch.setattr(router, "execute_tool", unexpected)
    monkeypatch.setattr(router, "detect_tool", unexpected)
    monkeypatch.setattr(router, "get_file_content", unexpected)
    monkeypatch.setattr(router, "add_message", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", lambda text: heard.append(text))
    router.process(command)
    assert heard == [command]


def test_conceptual_interrupted_turn_does_not_restart_streaming(monkeypatch):
    heard = []
    monkeypatch.setattr(router, "ask_ai", lambda text: heard.append(text) or "Explanation.")
    monkeypatch.setattr(router, "speak", lambda text: None)
    monkeypatch.setattr(router, "process_streaming_conversation", lambda text: pytest.fail("Must not restart interruption monitoring"))
    router.process("explain git status", allow_interruption=False)
    assert heard == ["explain git status"]


@pytest.mark.parametrize("command", ["do I have calendar access", "check my calendar", "check my email"])
def test_unavailable_integration_is_reported_without_execution_or_ai(monkeypatch, command):
    spoken = []
    def unexpected(*args, **kwargs):
        pytest.fail("Unavailable integration must not execute or guess")
    monkeypatch.setattr(router, "execute_capability", unexpected)
    monkeypatch.setattr(router, "execute_tool", unexpected)
    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    monkeypatch.setattr(router, "speak", spoken.append)
    router.process(command)
    assert len(spoken) == 1
    assert "not been configured" in spoken[0]

@pytest.mark.parametrize(
    "command",
    [
        "browse the web for Python 3.13 changes",
        "browse the internet for Python 3.13 changes",
    ],
)
def test_browser_research_routes_to_hermes(
    monkeypatch,
    command,
):
    requests = []

    class FakeAgent:
        available = True

    def fake_execute_agent(agent_name, task):
        requests.append((agent_name, task))

        return AgentExecutionResult(
            success=True,
            agent=agent_name,
            message="Research result.",
        )

    monkeypatch.setattr(
        router,
        "get_agent",
        lambda name: FakeAgent(),
    )
    monkeypatch.setattr(
        router,
        "execute_agent",
        fake_execute_agent,
    )
    monkeypatch.setattr(
        router,
        "speak",
        lambda text: None,
    )

    router.process(command)

    assert requests == [
        ("hermes", "python 3.13 changes")
    ]