from pathlib import Path
from types import SimpleNamespace
import runpy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from commands import actions, router
from models.database import Base
from models.session import Session
from models.conversation import Conversation
from models.memory import Memory
from models.tool_request import ToolRequest
from services import ai_service, conversation_service, conversation_manager as state
from services import conversation_lifecycle as lifecycle


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    lifecycle.reset_active_conversation()
    monkeypatch.setattr(conversation_service, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(ai_service, "update_status", lambda *a: None)
    monkeypatch.setattr(router, "speak", lambda *a: None)
    monkeypatch.setattr(actions, "speak", lambda *a: None)
    monkeypatch.setattr(router, "process_dynamic_command", lambda *a: False)
    yield
    lifecycle.reset_active_conversation()


def seed():
    conversation_service.conversation_history.append({"role": "user", "content": "old discussion", "source": "user"})
    state.set_topic({"type": "file", "filename": "old.py", "depth": 3})
    state.record_turn("user", "old file discussion")
    state.set_pending_request({"request": ToolRequest("explain_file"), "missing": "filename"})


def test_reset_is_idempotent_and_does_not_touch_persisted_records(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        session = Session()
        db.add(session)
        db.flush()
        db.add(Conversation(session_id=session.id, role="user", message="archived"))
        db.add(Memory(content="persistent personal fact"))
        db.commit()
        seed()
        lifecycle.reset_active_conversation()
        lifecycle.reset_active_conversation()
        assert conversation_service.get_conversation_history() == []
        assert state.get_conversation_context() == {"topic": None, "pending_request": None, "recent_turns": []}
        assert db.query(Session).count() == 1
        assert db.query(Conversation).one().message == "archived"
        assert db.query(Memory).one().content == "persistent personal fact"
    engine.dispose()


@pytest.mark.parametrize("phrase", ["That's all!", "Goodbye.", "thanks", "I'm done"])
def test_standalone_end_phrases(phrase):
    assert lifecycle.is_conversation_end(phrase)


@pytest.mark.parametrize("phrase", ["Explain why goodbye is printed", "What does thank you mean?", "that's all the code does"])
def test_embedded_end_phrases_are_not_boundaries(phrase):
    assert not lifecycle.is_conversation_end(phrase)


@pytest.mark.parametrize("boundary", ["timeout", "explicit_end", "interrupted_end"])
@pytest.mark.parametrize("exit_location", ["standby", "listening"])
def test_main_startup_standby_wake_and_exit(monkeypatch, boundary, exit_location):
    from services import listener, speaker, status_service, transcription_service, conversation_db
    from models import memory
    seed()
    monkeypatch.setattr(memory, "initialize_database", lambda: None)
    monkeypatch.setattr(conversation_service, "restore_recent_history", lambda *a, **k: pytest.fail("Must not restore archives"))
    monkeypatch.setattr(conversation_db, "start_session", lambda: None)
    ended = []
    monkeypatch.setattr(conversation_db, "end_session", lambda: ended.append(True))
    monkeypatch.setattr(listener, "calibrate_microphone", lambda: None)
    monkeypatch.setattr(transcription_service, "warm_up_transcription", lambda: None)
    monkeypatch.setattr(ai_service, "warm_up_ai", lambda: None)
    monkeypatch.setattr(speaker, "speak", lambda *a: None)
    monkeypatch.setattr(status_service, "update_status", lambda *a: None)
    monkeypatch.setattr(status_service, "update_last_command", lambda *a: None)
    wakes = iter([True, True, "exit"])
    monkeypatch.setattr(listener, "listen_for_wake_word", lambda: next(wakes))
    replies = iter([
        SimpleNamespace(text="seed", timed_out=False),
        SimpleNamespace(text={"explicit_end": "thanks", "interrupted_end": "end_stream"}.get(boundary, ""), timed_out=boundary == "timeout"),
        SimpleNamespace(text="inspect", timed_out=False),
        SimpleNamespace(text="exit" if exit_location == "listening" else "", timed_out=exit_location == "standby"),
    ])
    monkeypatch.setattr(listener, "listen_for_speech_result", lambda: next(replies))
    seen = []
    real_process = router.process
    monkeypatch.setattr(router, "stop_speaking", lambda: None)

    def process(command):
        if command == "seed":
            assert conversation_service.get_conversation_history() == []
            assert state.get_topic() is None
            seed()
        elif command == "end_stream":
            return real_process("That's all.")
        else:
            seen.append(state.get_conversation_context())
            assert bool(conversation_service.get_conversation_history()) == (boundary == "timeout")

    monkeypatch.setattr(router, "process", process)
    if exit_location == "listening":
        with pytest.raises(SystemExit):
            runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))
    else:
        runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))
    assert bool(seen[0]["topic"]) == (boundary == "timeout")
    assert bool(seen[0]["pending_request"]) == (boundary == "timeout")
    assert ended == [True]
    assert state.get_topic() is None
    assert conversation_service.get_conversation_history() == []


def test_file_rest_followup_and_explicit_return(monkeypatch):
    monkeypatch.setattr(actions, "find_matching_files", lambda name: [Path(name)])
    monkeypatch.setattr(actions, "get_file_content", lambda name: {"filename": name, "content": "FILE_SENTINEL"})
    monkeypatch.setattr(ai_service, "explain_code", lambda info, depth: "file explanation")
    executed = []

    def execute(request):
        executed.append(request)
        actions.explain_file_action(**request.arguments)

    monkeypatch.setattr(router, "execute_tool", execute)
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: [])
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "capability sentinel")
    monkeypatch.setattr(ai_service, "get_file_content", lambda name: {"content": "FILE_SENTINEL"})
    messages = []

    def chat(**kwargs):
        messages.append(kwargs["messages"])
        answer = {"message": {"content": "REST answer"}}
        return iter([answer]) if kwargs["stream"] else answer

    monkeypatch.setattr(ai_service, "chat", chat)
    router.process("explain commands/router.py")
    router.process("tell me more")
    assert executed[-1].arguments["depth"] == 2
    router.process("what is REST?", allow_interruption=False)
    router.process("tell me more", allow_interruption=False)
    assert len(executed) == 2
    assert all("FILE_SENTINEL" not in str(prompt) for prompt in messages)
    assert [m["content"] for m in messages[-1] if m["role"] == "user"] == ["what is rest", "tell me more"]
    assert state.get_topic()["depth"] == 2
    code_questions = []
    monkeypatch.setattr(router, "get_file_content", lambda name: {"filename": name, "content": "pass"})
    monkeypatch.setattr(router, "answer_question", lambda question, info: code_questions.append(question) or "code answer")
    router.process("how does this file work?")
    assert code_questions == ["how does this file work"]
    router.process("tell me more")
    assert executed[-1].arguments["depth"] == 3


@pytest.mark.parametrize("question", ["What is REST?", "Why is the sky blue?", "How does inheritance work?"])
def test_clear_new_question_leaves_pending_clarification(monkeypatch, question):
    seed()
    heard = []
    monkeypatch.setattr(router, "process_streaming_conversation", heard.append)
    router.process(question)
    assert heard == [question.lower().rstrip("?")]
    assert state.get_pending_request() is None
    assert state.get_topic()["filename"] == "old.py"


@pytest.mark.parametrize("question", ["What is REST?", "What about inheritance?", "Tell me more"])
def test_prompt_context_parity_after_nonfile_focus(monkeypatch, question):
    seed()
    state.clear_pending_request()
    state.mark_conversation_discussion()
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: [])
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "")
    monkeypatch.setattr(ai_service, "get_file_content", lambda name: pytest.fail("Stale file must not be read"))
    captured = []

    def chat(**kwargs):
        captured.append(kwargs["messages"])
        answer = {"message": {"content": "answer"}}
        return iter([answer]) if kwargs["stream"] else answer

    monkeypatch.setattr(ai_service, "chat", chat)
    for mode in ("normal", "stream_option", "generator"):
        conversation_service.clear_history()
        if mode == "generator":
            list(ai_service.stream_ai_response(question))
        else:
            ai_service.ask_ai(question, stream=mode == "stream_option")
    assert captured[0] == captured[1] == captured[2]
    assert captured[0][1:] == [{"role": "user", "content": question}]


@pytest.mark.parametrize("question", ["How does process() work?", "What about this function?", "Why is aliases here?", "Explain that"])
def test_clear_file_references_remain_eligible(question):
    from services.code_intent import should_use_file_context
    from services.intent_resolver import resolve_intent
    state.set_topic({"type": "file", "filename": "router.py"})
    assert should_use_file_context(question)
    assert resolve_intent(question).type in {"code_question", "follow_up"}


def test_cancelled_new_question_keeps_user_turn_without_reactivating_old_file(monkeypatch):
    import threading
    from services.cancellation import OperationCancelled
    from services.intent_resolver import resolve_intent
    state.set_topic({"type": "file", "filename": "old.py"})
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: [])
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "")
    event = threading.Event()
    monkeypatch.setattr(ai_service, "chat", lambda **kwargs: iter([
        {"message": {"content": "partial"}}, {"message": {"content": "late"}},
    ]))

    def stream(question):
        response = ai_service.stream_ai_response(question, cancellation_event=event)
        assert next(response) == "partial"
        event.set()
        next(response)

    monkeypatch.setattr(router, "process_streaming_conversation", stream)
    with pytest.raises(OperationCancelled):
        router.process("what is REST?")
    assert conversation_service.get_conversation_history() == [
        {"role": "user", "content": "what is rest", "source": "user"},
    ]
    assert state.get_topic()["filename"] == "old.py"
    assert resolve_intent("tell me more").type == "conversation"


@pytest.mark.parametrize("command,tool", [("explain router.py", "explain_file"),
                                         ("summarize router.py", "summarize_file")])
def test_explicit_operation_on_active_file_stays_deterministic(monkeypatch, command, tool):
    from services.intent_resolver import resolve_intent
    state.set_topic({"type": "file", "filename": "router.py"})
    executed = []
    monkeypatch.setattr(router, "execute_tool", executed.append)
    monkeypatch.setattr(router, "execute_migrated_tool_request", lambda request: False)
    monkeypatch.setattr(router, "answer_question", lambda *a: pytest.fail("Explicit operation must use tool"))
    assert resolve_intent(command).type == "tool"
    router.process(command)
    assert executed == [ToolRequest(tool, {"filename": "router.py"})]
