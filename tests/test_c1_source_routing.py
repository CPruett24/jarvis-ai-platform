import json
from dataclasses import replace
import pytest

from commands import router
from services import project_access as access, ai_service, conversation_manager as conversation
from services import capability_state, capability_registry
from services.source_answer import source_capability, validate_answer
from services.project_service import retrieve_project_sources


@pytest.fixture
def fixture_project(tmp_path, monkeypatch):
    projects, active, revision = access._projects.copy(), access._active, access._revision
    context = access.register_project("fixture", tmp_path)
    access.select_project("fixture")
    (tmp_path / "router.py").write_text("def route(command):\n    return command\n")
    (tmp_path / "actions.py").write_text("def act():\n    return True\n")
    (tmp_path / "conversation_history.py").write_text("def save_history(message):\n    return message\n")
    conversation.clear_topic()
    conversation.clear_pending_request()
    heard, saved, prompts = [], [], []
    monkeypatch.setattr(router, "speak", heard.append)
    monkeypatch.setattr(router, "add_message", lambda role, text, source: saved.append((role, text, source)))
    monkeypatch.setattr(router, "process_dynamic_command", lambda command: False)

    def unexpected(*a, **k):
        pytest.fail("Source request must not call conversation fallback or Hermes")

    monkeypatch.setattr(router, "process_streaming_conversation", unexpected)
    monkeypatch.setattr(router, "ask_ai", unexpected)
    monkeypatch.setattr(router, "execute_agent", unexpected)
    monkeypatch.setattr(router, "detect_tool", unexpected)

    def fake_chat(**kwargs):
        prompts.append(kwargs)
        payload = json.loads(kwargs["messages"][1]["content"])
        excerpts = payload["observed_excerpts"]
        return {"message": {"content": "The retrieved implementation defines this behavior. [" + excerpts[0]["source_id"] + "]"}}

    monkeypatch.setattr(ai_service, "chat", fake_chat)
    yield context, heard, saved, prompts
    access._projects, access._active, access._revision = projects, active, revision
    conversation.clear_topic()
    conversation.clear_pending_request()


@pytest.mark.parametrize("command,path,model_calls", [
    ("What does the router do?", "router.py:1", 1),
    ("Explain how this project handles conversation history.", "conversation_history.py:1", 1),
    ("What files are in this project?", "actions.py", 0),
    ("Summarize the file actions.py.", "actions.py:1", 0),
])
def test_representative_requests_use_retrieved_sources(fixture_project, command, path, model_calls):
    context, heard, saved, prompts = fixture_project
    router.process(command, allow_interruption=False)
    assert len(heard) == 1
    assert path in heard[0]
    assert len(prompts) == model_calls
    assert any(source == "observed" for _, _, source in saved)
    if model_calls:
        assert "untrusted" in prompts[0]["messages"][0]["content"]


def test_missing_evidence_cannot_fall_back(fixture_project):
    _, heard, saved, prompts = fixture_project
    router.process("What does missing.py do?", allow_interruption=False)
    assert not prompts
    assert len(heard) == 1 and "couldn't complete" in heard[0]
    assert not any(source == "observed" for _, _, source in saved)


@pytest.mark.parametrize("answer", ["Invented answer [Sfake]", "Uncited answer",
    "Claim [router.py:100–200]", "Claim [Sfake]\n\nAnother uncited claim"])
def test_invented_citations_fail_closed(fixture_project, monkeypatch, answer):
    _, heard, _, _ = fixture_project
    monkeypatch.setattr(ai_service, "chat", lambda **kwargs: {"message": {"content": answer}})
    router.process("What does the router do?", allow_interruption=False)
    assert "valid source references" in heard[0]
    assert conversation.get_topic() is None


@pytest.mark.parametrize("command", [
    "Tell me how this project handles conversation history",
    "Explain how the router handles commands",
    "Find out how this project handles conversation history",
])
@pytest.mark.parametrize("invalid", [
    "Uncited answer", "Claim [source_id]", "Claim [Sfake]",
    "Claim [router.py:999]", "Claim [invented.yaml:1]",
    "Claim [router.py:2-1]",
])
def test_reported_paraphrases_regenerate_from_same_evidence(
        fixture_project, monkeypatch, command, invalid):
    _, heard, saved, _ = fixture_project
    calls = []
    def chat(**kwargs):
        # Copy messages: generation adds retry instructions after the first call.
        calls.append(json.loads(json.dumps(kwargs)))
        excerpt = json.loads(kwargs["messages"][1]["content"])["observed_excerpts"][0]
        answer = invalid if len(calls) == 1 else "Retrieved implementation. [" + excerpt["source_id"] + "]"
        return {"message": {"content": answer}}
    monkeypatch.setattr(ai_service, "chat", chat)
    router.process(command, allow_interruption=False)
    assert len(calls) == 2 and len(heard) == 1
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    assert "failed source-reference validation" in calls[1]["messages"][0]["content"]
    assert invalid not in calls[1]["messages"][1]["content"]
    assert "Interpretation of retrieved source" in heard[0]
    assert any(source == "observed" for _, _, source in saved)


def test_failed_regeneration_is_bounded_and_not_published(fixture_project, monkeypatch):
    _, heard, saved, _ = fixture_project
    calls = []
    def chat(**kwargs):
        calls.append(kwargs)
        return {"message": {"content": "Unverified generated prose"}}
    monkeypatch.setattr(ai_service, "chat", chat)
    router.process("What does the router do?", allow_interruption=False)
    assert len(calls) == 2
    assert "after one regeneration" in heard[0]
    assert "Unverified generated prose" not in heard[0]
    assert not any(source == "observed" for _, _, source in saved)
    assert conversation.get_topic() is None


def test_cancellation_during_regeneration_discards_valid_late_answer(fixture_project, monkeypatch):
    import threading
    from services.cancellation import OperationCancelled
    _, heard, saved, _ = fixture_project
    event = threading.Event()
    calls = []
    def chat(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"message": {"content": "Uncited answer"}}
        event.set()
        excerpt = json.loads(kwargs["messages"][1]["content"])["observed_excerpts"][0]
        return {"message": {"content": "Claim [" + excerpt["source_id"] + "]"}}
    monkeypatch.setattr(ai_service, "chat", chat)
    with pytest.raises(OperationCancelled):
        source_capability(filename="router.py", cancellation_event=event)
    assert len(calls) == 2
    assert not heard and not saved and conversation.get_topic() is None


def test_source_edit_during_retry_is_still_rejected(fixture_project, monkeypatch):
    context, heard, _, _ = fixture_project
    calls = []
    def chat(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"message": {"content": "Uncited"}}
        (context.root / "router.py").write_text("changed\n")
        excerpt = json.loads(kwargs["messages"][1]["content"])["observed_excerpts"][0]
        return {"message": {"content": "Claim [" + excerpt["source_id"] + "]"}}
    monkeypatch.setattr(ai_service, "chat", chat)
    router.process("What does the router do?", allow_interruption=False)
    assert len(calls) == 2 and "changed while answering" in heard[0]


def test_changed_source_during_generation_is_rejected(fixture_project, monkeypatch):
    context, heard, _, _ = fixture_project
    def edit(**kwargs):
        excerpt = json.loads(kwargs["messages"][1]["content"])["observed_excerpts"][0]
        (context.root / "router.py").write_text("def changed():\n    pass\n")
        return {"message": {"content": "Claim [" + excerpt["source_id"] + "]"}}
    monkeypatch.setattr(ai_service, "chat", edit)
    router.process("What does the router do?", allow_interruption=False)
    assert "changed while answering" in heard[0]


def test_duplicate_clarification_rechecks_capability_and_authorization(fixture_project, monkeypatch):
    context, heard, _, prompts = fixture_project
    (context.root / "nested").mkdir()
    (context.root / "nested" / "router.py").write_text("def nested():\n    pass\n")
    router.process("What does router.py do?", allow_interruption=False)
    assert conversation.get_pending_request()["source_grounded"]
    monkeypatch.setattr(capability_state, "_DISABLED_CAPABILITIES", {"code_explanation"})
    router.process("nested/router.py", allow_interruption=False)
    assert not prompts and "disabled" in heard[-1]
    monkeypatch.setattr(capability_state, "_DISABLED_CAPABILITIES", set())
    router.process("What does router.py do?", allow_interruption=False)
    access.register_project("fixture", context.root)
    router.process("nested/router.py", allow_interruption=False)
    assert "authorization changed" in heard[-1].lower()


def test_file_edit_between_turns_is_retrieved_again(fixture_project):
    context, heard, _, prompts = fixture_project
    router.process("What does the router do?", allow_interruption=False)
    (context.root / "router.py").write_text("def route(command):\n    return 'new'\n")
    router.process("Tell me more", allow_interruption=False)
    assert len(prompts) == 2
    assert "new" in prompts[-1]["messages"][1]["content"]


@pytest.mark.parametrize("command", ["What is inheritance?", "What is a router?"])
def test_conceptual_questions_remain_conversation(fixture_project, monkeypatch, command):
    heard = []
    monkeypatch.setattr(router, "_ask_and_speak", heard.append)
    router.process(command, allow_interruption=False)
    assert heard == [command.lower().rstrip("?")]


def test_stale_topic_follow_up_cannot_become_chat(fixture_project):
    context, heard, _, prompts = fixture_project
    router.process("What does the router do?", allow_interruption=False)
    access.register_project("fixture", context.root)
    router.process("Tell me more", allow_interruption=False)
    assert len(prompts) == 1
    assert "authorization changed" in heard[-1]


@pytest.mark.parametrize("command", ["analyze this project", "analyze these files", "investigate router.py"])
def test_source_analysis_never_delegates_to_hermes(fixture_project, command):
    _, heard, _, _ = fixture_project
    router.process(command, allow_interruption=False)
    assert len(heard) == 1


@pytest.mark.parametrize("during_retry", [False, True])
def test_cancelled_source_generation_cannot_commit_late_evidence(fixture_project, monkeypatch, during_retry):
    import threading
    from types import SimpleNamespace
    _, _, saved, _ = fixture_project
    started, release, cancelled = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(router, "_conversation_producer_slot", threading.BoundedSemaphore(1))
    calls = []
    def blocked_chat(**kwargs):
        calls.append(kwargs)
        if during_retry and len(calls) == 1:
            return {"message": {"content": "Uncited answer"}}
        started.set()
        assert release.wait(2)
        excerpt = json.loads(kwargs["messages"][1]["content"])["observed_excerpts"][0]
        return {"message": {"content": "Claim [" + excerpt["source_id"] + "]"}}
    monkeypatch.setattr(ai_service, "chat", blocked_chat)
    yielded = []
    worker = threading.Thread(target=lambda: yielded.extend(router._stream_with_interrupt(
        "question", SimpleNamespace(interrupted=cancelled),
        lambda event: router.stream_source_response({"question": "What does router do?",
            "filename": "router.py", "operation": "read"}, event))))
    worker.start()
    try:
        assert started.wait(1)
        cancelled.set()
        worker.join(1)
        assert not worker.is_alive()
    finally:
        cancelled.set()
        release.set()
        worker.join(2)
    assert router._conversation_producer_slot.acquire(timeout=1)
    router._conversation_producer_slot.release()
    assert yielded == [] and saved == [] and conversation.get_topic() is None


def test_discover_and_select_only_authorized_projects(fixture_project):
    _, heard, _, prompts = fixture_project
    router.process("List authorized projects", allow_interruption=False)
    assert "fixture" in heard[-1] and "jarvis" in heard[-1]
    router.process("Select project missing", allow_interruption=False)
    assert "not authorized" in heard[-1] and access.get_project().project_id == "fixture"
    router.process("Select project jarvis", allow_interruption=False)
    assert access.get_project().project_id == "jarvis" and not prompts


def test_read_source_is_deterministic_and_preserves_blank_lines(fixture_project):
    _, heard, saved, prompts = fixture_project
    router.process("Show the file router.py", allow_interruption=False)
    assert "Observed source [router.py:1" in heard[-1]
    assert "1: def route(command):" in heard[-1]
    assert not prompts


def test_conceptual_explanation_with_additional_project_is_conversation(fixture_project, monkeypatch):
    heard = []
    monkeypatch.setattr(router, "_ask_and_speak", heard.append)
    router.process("Explain inheritance", allow_interruption=False)
    assert heard == ["explain inheritance"]


@pytest.mark.parametrize("command,operation", [
    ("Tell me how this project handles conversation history", "search"),
    ("Explain how the router handles commands", "read"),
    ("Find out how this project handles conversation history", "search"),
    ("Describe why our project stores conversation history", "search"),
    ("Research conversation history in this project", "search"),
    ("Walk me through how my project saves messages", "search"),
    ("Tell me why the command parser processes commands", "read"),
    ("Find out how our router routes requests", "read"),
    ("How does the router handle commands", "read"),
    ("Walk me through how the command parser processes commands", "read"),
    ("Tell me about my project", "search"),
])
def test_project_paraphrases_retrieve_before_any_fallback(fixture_project, command, operation):
    from services.code_intent import resolve_source_request
    context, heard, saved, prompts = fixture_project
    (context.root / "command_parser.py").write_text("def parse(command):\n    return command\n")
    assert resolve_source_request(command)["operation"] == operation
    router.process(command, allow_interruption=False)
    assert len(heard) == len(prompts) == 1
    assert "Interpretation of retrieved source" in heard[0]
    assert any(source == "observed" for _, _, source in saved)


@pytest.mark.parametrize("command", [
    "Tell me how this project handles conversation history",
    "Explain how the router handles commands",
    "Find out how this project handles conversation history",
])
def test_reported_paraphrases_fail_closed_without_source(fixture_project, command):
    context, heard, saved, prompts = fixture_project
    for path in context.root.glob("*.py"):
        path.unlink()
    router.process(command, allow_interruption=False)
    assert len(heard) == 1 and "couldn't complete" in heard[0]
    assert not prompts and not any(source == "observed" for _, _, source in saved)


@pytest.mark.parametrize("command", [
    "What is inheritance?", "What is a router?", "Explain Python decorators.",
    "What is a project?", "Explain what a project manager does",
    "Tell me about a school project", "Explain how a router handles packets",
    "Explain how the network router handles packets", "How should I file my taxes?",
    "What is a file format?", "Tell me about the project management triangle",
])
def test_non_project_word_mentions_remain_conceptual(fixture_project, monkeypatch, command):
    from services.code_intent import resolve_source_request
    assert resolve_source_request(command) is None
    heard = []
    monkeypatch.setattr(router, "_ask_and_speak", heard.append)
    router.process(command, allow_interruption=False)
    assert heard == [command.lower().rstrip("?.")]
