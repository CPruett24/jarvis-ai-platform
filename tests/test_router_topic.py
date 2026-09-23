from pathlib import Path

import pytest

from commands import actions, router
from services import ai_service
from services import conversation_manager as conversation


@pytest.fixture(autouse=True)
def isolate_state():
    conversation.clear_topic()
    conversation.clear_pending_request()
    conversation.clear_context()
    yield
    conversation.clear_topic()
    conversation.clear_pending_request()
    conversation.clear_context()


@pytest.fixture
def file_actions(monkeypatch):
    explained = []
    monkeypatch.setattr(actions, "speak", lambda text: None)
    monkeypatch.setattr(actions, "find_matching_files", lambda name: [Path(name)])
    monkeypatch.setattr(actions, "get_file_content", lambda name: {
        "filename": name, "content": "pass",
    })

    def explain(info, depth):
        explained.append((info["filename"], depth))
        return "Explanation."

    def execute(request):
        assert request.tool == "explain_file"
        actions.explain_file_action(**request.arguments)

    monkeypatch.setattr(ai_service, "explain_code", explain)
    monkeypatch.setattr(router, "execute_tool", execute)
    return explained


def test_switch_commits_new_file_and_follow_ups_use_its_depth(file_actions):
    conversation.set_topic({"type": "file", "filename": "old.py", "depth": 4})
    router.process("next explain new.py")
    assert conversation.get_topic() == {"type": "file", "filename": "new.py", "depth": 1}
    router.process("tell me more")
    router.process("continue")
    assert file_actions == [("new.py", 1), ("new.py", 2), ("new.py", 3)]
    assert conversation.get_topic()["depth"] == 3


@pytest.mark.parametrize("failure", ["not_found", "unreadable", "ambiguous", "generation"])
def test_failed_file_handling_does_not_commit_topic_or_depth(monkeypatch, file_actions, failure):
    conversation.set_topic({"type": "file", "filename": "old.py", "depth": 4})
    before = conversation.get_topic()
    if failure == "not_found":
        monkeypatch.setattr(actions, "find_matching_files", lambda name: [])
    elif failure == "unreadable":
        monkeypatch.setattr(actions, "get_file_content", lambda name: None)
    elif failure == "ambiguous":
        monkeypatch.setattr(actions, "find_matching_files", lambda name: [Path("a.py"), Path("b.py")])
    else:
        def fail(*args):
            raise RuntimeError("generation failed")
        monkeypatch.setattr(ai_service, "explain_code", fail)

    for command in ["next explain new.py", "tell me more"]:
        if failure == "generation":
            with pytest.raises(RuntimeError, match="generation failed"):
                router.process(command)
        else:
            router.process(command)
        assert conversation.get_topic() == before
    assert file_actions == []


def test_unsupported_topic_does_not_enter_file_discussion(monkeypatch):
    conversation.set_topic({"type": "unsupported"})
    def unexpected(*args):
        pytest.fail("Unsupported topic must not be used as a file")
    monkeypatch.setattr(router, "get_file_content", unexpected)
    monkeypatch.setattr(router, "detect_tool", lambda command: "none")
    monkeypatch.setattr(router, "ask_ai", lambda *args, **kwargs: "No file context.")
    monkeypatch.setattr(router, "speak", lambda text: None)
    router.process("why", allow_interruption=False)
