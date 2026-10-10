from pathlib import Path

import pytest

from commands import actions, router
from models.tool_request import ToolRequest
from services import conversation_manager as conversation
from services import project_service
from services.intent_resolver import resolve_intent


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    conversation.clear_topic()
    conversation.clear_pending_request()
    monkeypatch.setattr(project_service, "find_matching_files", lambda name: [])
    monkeypatch.setattr(router, "process_dynamic_command", lambda command: False)
    monkeypatch.setattr(router, "speak", lambda text: None)
    yield
    conversation.clear_topic()
    conversation.clear_pending_request()


def fail_tool(*args, **kwargs):
    pytest.fail("Conceptual follow-up must not execute a file tool")


@pytest.mark.parametrize("topic", [None, {"type": "chat"},
    {"type": "file", "filename": "stale.py", "depth": 4}])
@pytest.mark.parametrize("command", ["What about inheritance?",
    "What about polymorphism?", "How about encapsulation?", "What about Python?"])
def test_conceptual_transitions_classify_and_execute_as_conversation(monkeypatch, topic, command):
    if topic:
        conversation.set_topic(topic)
    before = conversation.get_topic()
    heard = []
    monkeypatch.setattr(router, "execute_tool", fail_tool)
    monkeypatch.setattr(router, "detect_tool", fail_tool)
    monkeypatch.setattr(router, "process_streaming_conversation", heard.append)
    assert resolve_intent(command).type == "conversation"
    router.process(command)
    assert heard == [command.lower().rstrip("?")]
    assert conversation.get_topic() == before


def test_oop_follow_up_uses_actual_router_conversation_path(monkeypatch):
    heard = []
    monkeypatch.setattr(router, "execute_tool", fail_tool)
    monkeypatch.setattr(router, "process_streaming_conversation", heard.append)
    router.process("What is object-oriented?")
    router.process("What about inheritance?")
    assert heard == ["what is object-oriented", "what about inheritance"]


@pytest.mark.parametrize("prefix", ["what about", "how about", "switch to"])
@pytest.mark.parametrize("target", ["router.py", "missing.py", "services/router.py",
                                       r"services\router.py"])
def test_explicit_targets_share_classification_and_execution(monkeypatch, prefix, target):
    command = f"{prefix} {target}?"
    intent = resolve_intent(command)
    assert intent.type == "topic_switch"
    executed = []
    monkeypatch.setattr(router, "resolve_intent", lambda text: intent)
    monkeypatch.setattr(router, "execute_tool", executed.append)
    monkeypatch.setattr(router, "process_streaming_conversation", fail_tool)
    router.process(command)
    assert executed == [ToolRequest("explain_file", {"filename": target, "depth": 1})]
    assert executed[0] is intent.tool_request


@pytest.mark.parametrize("prefix", ["what about", "how about"])
def test_extensionless_target_requires_file_context_and_project_evidence(monkeypatch, prefix):
    monkeypatch.setattr(project_service, "find_matching_files", lambda name: [Path("router.py")])
    assert resolve_intent(f"{prefix} router").type == "conversation"
    conversation.set_topic({"type": "file", "filename": "old.py"})
    executed = []
    monkeypatch.setattr(router, "execute_tool", executed.append)
    router.process(f"{prefix} router")
    assert executed == [ToolRequest("explain_file", {"filename": "router", "depth": 1})]


@pytest.mark.parametrize("prefix", ["what about", "how about"])
def test_other_file_asks_for_filename_without_inventing_target(monkeypatch, prefix):
    spoken = []
    monkeypatch.setattr(actions, "speak", spoken.append)
    monkeypatch.setattr(router, "execute_tool", lambda request:
                        actions.explain_file_action(**request.arguments))
    router.process(f"{prefix} the other file?")
    pending = conversation.get_pending_request()
    assert pending["missing"] == "filename"
    assert pending["request"].arguments == {}
    assert spoken == ["Sure. Which file would you like me to explain?"]


@pytest.mark.parametrize("prefix", ["what about", "how about"])
def test_conceptual_transition_does_not_abandon_pending_filename(monkeypatch, prefix):
    pending = {"request": ToolRequest("explain_file"), "missing": "filename",
               "prompt": "Which file?"}
    conversation.set_pending_request(pending)
    spoken = []
    monkeypatch.setattr(router, "speak", spoken.append)
    monkeypatch.setattr(router, "execute_tool", fail_tool)
    router.process(f"{prefix} inheritance?")
    assert conversation.get_pending_request() is pending
    assert spoken == ["Which file?"]


@pytest.mark.parametrize("command", ["what about missing.py", "how about missing.py",
                                      "explain missing.py"])
def test_missing_explicit_filename_reports_failure_and_preserves_topic(monkeypatch, command):
    conversation.set_topic({"type": "file", "filename": "old.py", "depth": 3})
    before = conversation.get_topic()
    conversation.set_pending_request({"request": ToolRequest("explain_file"), "missing": "filename"})
    monkeypatch.setattr(actions, "find_matching_files", lambda name: [])
    spoken = []
    monkeypatch.setattr(actions, "speak", spoken.append)
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    monkeypatch.setattr(router, "execute_tool", lambda request:
                        actions.explain_file_action(**request.arguments))
    router.process(command)
    assert "couldn't find a file named missing.py" in spoken[0]
    assert conversation.get_topic() == before
    assert not conversation.has_pending_request()


def test_missing_explicit_explain_without_topic_stays_deterministic(monkeypatch):
    executed = []
    monkeypatch.setattr(router, "execute_tool", executed.append)
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    monkeypatch.setattr(router, "process_streaming_conversation", fail_tool)
    router.process("explain missing.py")
    assert executed == [ToolRequest("explain_file", {"filename": "missing.py"})]


def test_explicit_project_paths_resolve_exactly_within_project(monkeypatch, tmp_path):
    directory = tmp_path / "services"
    directory.mkdir()
    target = directory / "router.py"
    target.write_text("pass\n")
    monkeypatch.setattr(project_service, "_project_root", lambda: tmp_path)
    assert project_service._find_matching_files("services/router.py") == [target]
    assert project_service._find_matching_files(r"services\router.py") == [target]
    assert project_service._find_matching_files("services/missing.py") == []
    assert project_service._find_matching_files("../outside.py") == []


def test_ambiguous_extensionless_target_uses_existing_candidate_clarification(monkeypatch):
    conversation.set_topic({"type": "file", "filename": "old.py"})
    candidates = [Path("router.py"), Path("test_router.py")]
    monkeypatch.setattr(project_service, "find_matching_files", lambda name: candidates)
    monkeypatch.setattr(actions, "find_matching_files", lambda name: candidates)
    monkeypatch.setattr(actions, "speak", lambda text: None)
    monkeypatch.setattr(router, "execute_tool", lambda request:
                        actions.explain_file_action(**request.arguments))
    router.process("how about router")
    assert conversation.get_pending_request()["candidates"] == candidates
    completed = conversation.complete_pending_request("test_router.py")
    assert completed.arguments == {"filename": "test_router.py"}
    assert conversation.get_topic()["filename"] == "old.py"
