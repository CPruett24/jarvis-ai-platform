import pytest

from commands import actions, router
from services import ai_service, conversation_service, project_service
from services import conversation_manager as state
from services import conversation_lifecycle as lifecycle


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    lifecycle.reset_active_conversation()
    monkeypatch.setattr(conversation_service, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(router, "stop_speaking", lambda: None)
    monkeypatch.setattr(router, "speak", lambda *a: None)
    monkeypatch.setattr(actions, "speak", lambda *a: None)
    monkeypatch.setattr(ai_service, "update_status", lambda *a: None)
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: [])
    monkeypatch.setattr(router, "process_dynamic_command", lambda *a: False)
    yield
    lifecycle.reset_active_conversation()


@pytest.mark.parametrize("command", ["That's all!", "Goodbye.", "Thanks"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_end_command_stops_resets_and_returns_control(monkeypatch, command, wrapped):
    state.set_topic({"type": "file", "filename": "router.py"})
    state.set_pending_request({"missing": "filename"})
    state.record_turn("user", "old")
    conversation_service.conversation_history.append({"role": "user", "content": "old"})
    stopped = []
    monkeypatch.setattr(router, "stop_speaking", lambda: stopped.append(True))
    monkeypatch.setattr(router, "ask_ai", lambda *a: pytest.fail("End must not reach Ollama"))
    monkeypatch.setattr(router, "process_streaming_conversation", lambda *a: pytest.fail("End must not start speech"))
    if wrapped:
        command = router.INTERRUPTION_PREFIX + command
    assert router.process(command) is lifecycle.CONVERSATION_ENDED
    assert stopped == [True]
    assert conversation_service.get_conversation_history() == []
    assert state.get_conversation_context() == {"topic": None, "pending_request": None, "recent_turns": []}


@pytest.mark.parametrize("question", ["what is REST?", "explain REST"])
def test_real_stream_interruption_propagates_end(monkeypatch, question):
    callbacks = []
    events = []

    class Speech:
        def start_response(self):
            pass

        def add_chunk(self, text):
            callbacks[0]("That's all")

        def interrupt(self):
            events.append("stopped")

    class Monitor:
        def __init__(self, callback):
            callbacks.append(callback)

        def start(self):
            pass

        def stop(self):
            events.append("monitor_stopped")

    monkeypatch.setattr(router, "ConversationSpeech", Speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", Monitor)
    monkeypatch.setattr(router, "stream_ai_response", lambda *a, **k: iter(["REST explanation"]))
    monkeypatch.setattr(router, "get_file_content", lambda *a: None)
    monkeypatch.setattr(router, "ask_ai", lambda *a: pytest.fail("Ending must not trigger another answer"))
    assert router.process(question) is lifecycle.CONVERSATION_ENDED
    assert "stopped" in events and "monitor_stopped" in events
    assert conversation_service.get_conversation_history() == []


@pytest.mark.parametrize("command", ["stop", "wait", "explain why goodbye is printed", "what does thank you mean?"])
def test_other_interruptions_are_not_end_commands(monkeypatch, command):
    heard = []
    monkeypatch.setattr(router, "ask_ai", lambda text: heard.append(text) or "answer")
    monkeypatch.setattr(router, "get_file_content", lambda *a: None)
    monkeypatch.setattr(router, "process_streaming_conversation", lambda text: heard.append(text) or "answer")
    assert router.process(router.INTERRUPTION_PREFIX + command) is not lifecycle.CONVERSATION_ENDED
    if command in {"stop", "wait"}:
        assert heard == []
    else:
        assert heard == [command.rstrip("?")]


def test_full_file_timeout_end_sequence_uses_actual_router_and_prompt(monkeypatch, tmp_path):
    target = tmp_path / "example.py"
    target.write_text("FILE_SENTINEL = True\n")
    monkeypatch.setattr(project_service, "_project_root", lambda: tmp_path)
    monkeypatch.setattr(ai_service, "explain_code", lambda info, depth: f"file depth {depth}")
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    executed = []

    def execute(request):
        executed.append(request)
        actions.explain_file_action(**request.arguments)

    monkeypatch.setattr(router, "execute_tool", execute)
    prompts = []

    def chat(**kwargs):
        prompts.append(kwargs["messages"])
        return {"message": {"content": "General explanation."}}

    monkeypatch.setattr(ai_service, "chat", chat)
    router.process("explain example.py")
    assert state.get_topic()["filename"] == "example.py"
    router.process("tell me more")
    assert state.get_topic()["depth"] == 2
    router.process("what is REST?", allow_interruption=False)
    assert not state.is_file_discussion_active()
    router.process("tell me more", allow_interruption=False)
    lifecycle.handle_conversation_boundary("timeout")
    router.process("tell me more", allow_interruption=False)
    assert len(executed) == 2
    assert all("FILE_SENTINEL" not in str(prompt) for prompt in prompts)
    assert [m["content"] for m in prompts[-1] if m["role"] == "user"] == ["what is rest", "tell me more", "tell me more"]
    assert router.process("that's all") is lifecycle.CONVERSATION_ENDED
    router.process("what is inheritance?", allow_interruption=False)
    assert state.get_topic() is None
    assert prompts[-1][1:] == [{"role": "user", "content": "what is inheritance"}]


def test_generic_prompt_exposes_assistant_claim_as_context_not_evidence(monkeypatch):
    conversation_service.conversation_history.extend([
        {"role": "user", "content": "ExplainMain.py", "source": "user"},
        {"role": "assistant", "content": "Your project uses REST extensively.", "source": "ollama"},
    ])
    # Real capability context and real memory selector; no stored personal facts.
    prompt = ai_service._build_conversation_messages("What is inheritance?")
    assert prompt[-1] == {"role": "assistant", "content": "Your project uses REST extensively."}
    system = prompt[0]["content"]
    assert "NOT evidence" in system
    assert "without gratuitous personalization" in system
    assert "Your project uses REST extensively." not in system
    assert "Current file contents" not in system
    assert "[remembered]" not in system.split("CAPABILITY RULES:")[0]
