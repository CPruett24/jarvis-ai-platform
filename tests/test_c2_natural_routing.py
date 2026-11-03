"""Natural C2 requests through real routing, with simulated voice and isolated roots."""
from pathlib import Path
from types import SimpleNamespace
import runpy

import pytest

from commands import router
from services import project_access as access, capability_state, conversation_manager
from services.code_intent import resolve_relationship_request


FAILED_SENTENCE = "What functions call the speak function in my Jarvis project?"


@pytest.fixture
def project(tmp_path, monkeypatch):
    old = access._projects.copy(), access._active, access._revision
    disabled = capability_state._DISABLED_CAPABILITIES.copy()
    access._projects = {}
    access.register_project("Jarvis", tmp_path)
    access.select_project("Jarvis")
    capability_state._DISABLED_CAPABILITIES.discard("multi_file_reasoning")
    conversation_manager.clear_topic()
    conversation_manager.clear_pending_request()
    (tmp_path / "voice.py").write_text("def speak():\n    pass\ndef Speak():\n    pass\ndef Caller():\n    speak()\n    Speak()\n")
    heard, saved = [], []
    monkeypatch.setattr(router, "speak", heard.append)
    monkeypatch.setattr(router, "add_message", lambda role, text, source: saved.append((role, text, source)))
    def forbidden(*a, **k):
        pytest.fail("A recognized relationship request must never use AI/Hermes or legacy analysis")
    for name in ("ask_ai", "detect_tool", "execute_agent", "process_streaming_conversation",
                 "refresh_project_analysis_if_changed"):
        monkeypatch.setattr(router, name, forbidden)
    yield tmp_path, heard, saved
    access._projects, access._active, access._revision = old
    capability_state._DISABLED_CAPABILITIES = disabled
    conversation_manager.clear_topic()
    conversation_manager.clear_pending_request()


@pytest.mark.parametrize("sentence", [
    FAILED_SENTENCE, "What functions call speak?", "What functions call the speak function?",
    "Which functions call speak?", "What methods call speak?", "Who calls speak?", "What calls speak?",
    "Which methods call the method speak?", "What calls speak() in project Jarvis?",
    "What calls the function speak in my project?",
])
def test_caller_variants_parser_and_actual_dispatch(project, sentence):
    request = resolve_relationship_request(sentence)
    assert request["operation"] == "calls" and request["direction"] == "reverse"
    assert request["qualified_name"] == "speak"
    if sentence == FAILED_SENTENCE:
        assert request["project_qualifier"] == "Jarvis"
    result = router.process(sentence, allow_interruption=False)
    assert result.success and result.capability == "multi_file_reasoning"
    assert "Caller" in result.data["response"] and "[voice.py:" in result.data["response"]


@pytest.mark.parametrize("target", ["Speak", "voice.py::Speak", "./voice.py::Speak"])
def test_target_case_is_preserved(project, target):
    request = resolve_relationship_request(f"Which methods call the {target} method in my jArViS project?")
    assert request["qualified_name"] == "Speak"
    result = router.process(f"Which methods call the {target} method in my jArViS project?", allow_interruption=False)
    assert result.success and result.data["topic"]["qualified_name"] == "Speak"


@pytest.mark.parametrize("operation", ["What depends on voice.py", "What does voice.py import",
                                        "Trace voice.py::Speak forward", "Impact of changing Speak"])
def test_project_qualifier_is_separate_for_other_relationships(project, operation):
    request = resolve_relationship_request(operation + " in my Jarvis project?")
    assert request["project_qualifier"] == "Jarvis"
    result = router.process(operation + " in my Jarvis project?", allow_interruption=False)
    assert result.capability == "multi_file_reasoning"


@pytest.mark.parametrize("sentence", ["What functions does Caller call?", "Which methods does Caller call?"])
def test_natural_forward_questions_keep_direction(project, sentence):
    request = resolve_relationship_request(sentence)
    assert request["direction"] == "forward" and request["qualified_name"] == "Caller"
    assert router.process(sentence, allow_interruption=False).success


@pytest.mark.parametrize("kind", ["unknown", "mismatch", "revoked"])
def test_named_project_never_authorizes_or_switches(project, kind):
    root, heard, saved = project
    if kind == "unknown":
        command = "What functions call speak in my Unknown project?"
    else:
        other = root / "other"
        other.mkdir()
        access.register_project("Other", other)
        if kind == "revoked":
            access.revoke_project("Other")
            command = "What functions call speak in my Other project?"
        else:
            access.select_project("Other")
            command = FAILED_SENTENCE
    previous = access._projects.copy(), access._active
    router.process(command, allow_interruption=False)
    assert "active authorized project" in heard[-1]
    assert (access._projects, access._active) == previous
    assert not saved


@pytest.mark.parametrize("sentence", ["What functions call?", "What functions call the function?",
                                       "What functions call speak with some extra words?", "Who calls file.py::?"])
def test_malformed_target_is_explicit_not_conversation(project, sentence):
    request = resolve_relationship_request(sentence)
    assert request is not None
    router.process(sentence, allow_interruption=False)
    assert "specify" in project[1][-1].lower() or "find" in project[1][-1].lower()


@pytest.mark.parametrize("failure", ["missing", "duplicate", "disabled", "incomplete"])
def test_capability_failures_never_fall_back(project, failure):
    root, heard, saved = project
    command = FAILED_SENTENCE
    if failure == "missing":
        command = "What functions call missing in my Jarvis project?"
    elif failure == "duplicate":
        (root / "duplicate.py").write_text("def speak():\n    pass\n")
    elif failure == "disabled":
        capability_state._DISABLED_CAPABILITIES.add("multi_file_reasoning")
    else:
        (root / "broken.py").write_text("def broken(:\n")
    result = router.process(command, allow_interruption=False)
    assert not result.success and heard
    assert not any(source == "observed" for _, _, source in saved)


@pytest.mark.parametrize("sentence", ["Explain voice.py", "What is a call graph?",
                                       "How do function calls work?", "What did we discuss about speak yesterday?"])
def test_precedence_and_conceptual_compatibility(project, monkeypatch, sentence):
    assert resolve_relationship_request(sentence) is None
    calls = []
    monkeypatch.setattr(router, "_ask_and_speak", lambda text: calls.append(("conversation", text)))
    monkeypatch.setattr(router, "execute_registered_capability", lambda name, *a, **k:
                        calls.append((name, k)) or SimpleNamespace(success=True))
    router.process(sentence, allow_interruption=False)
    assert calls and calls[0][0] == ("project_source" if sentence == "Explain voice.py" else "conversation")


def test_interrupted_qualified_request_preserves_case_and_path(project, monkeypatch):
    monkeypatch.setattr(router, "process_streaming_conversation", lambda command, stream_factory:
        router.execute_registered_capability("multi_file_reasoning", resolve_args(command)))
    def resolve_args(command):
        return {**resolve_relationship_request(command), "context": access.get_project()}
    result = router.process(router.INTERRUPTION_PREFIX + "Wait, stop, Which functions call voice.py::Speak?")
    assert result.success and result.data["topic"]["qualified_name"] == "Speak"


def test_listener_preserves_case_and_wake_detection_stays_insensitive(project, monkeypatch):
    from services import listener
    class FakeMicrophone:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(listener, "microphone", FakeMicrophone())
    monkeypatch.setattr(listener.recognizer, "listen", lambda *a, **k:
                        SimpleNamespace(frame_data=b"00", sample_rate=1, sample_width=1))
    monkeypatch.setattr(listener, "transcribe_audio", lambda *a: "Which functions call voice.py::Speak?")
    assert listener.listen_for_speech_result().text == "Which functions call voice.py::Speak?"
    monkeypatch.setattr(listener, "listen_for_speech", lambda: "JARVIS")
    assert listener.listen_for_wake_word()
    monkeypatch.setattr(listener, "listen_for_speech", lambda: "EXIT")
    assert listener.listen_for_wake_word() == "exit"


@pytest.mark.parametrize("clarification", [False, True])
def test_simulated_main_passes_case_to_actual_capability(project, monkeypatch, clarification):
    from services import listener, speaker, status_service, transcription_service, conversation_db, ai_service
    from models import memory
    monkeypatch.setattr(memory, "initialize_database", lambda: None)
    for name in ("start_session", "end_session"):
        monkeypatch.setattr(conversation_db, name, lambda: None)
    monkeypatch.setattr(listener, "calibrate_microphone", lambda: None)
    monkeypatch.setattr(transcription_service, "warm_up_transcription", lambda: None)
    monkeypatch.setattr(ai_service, "warm_up_ai", lambda: None)
    monkeypatch.setattr(speaker, "speak", lambda *a: None)
    monkeypatch.setattr(status_service, "update_status", lambda *a: None)
    monkeypatch.setattr(status_service, "update_last_command", lambda *a: None)
    wakes = iter([True, "exit"])
    monkeypatch.setattr(listener, "listen_for_wake_word", lambda: next(wakes))
    inputs = ["Which functions call voice.py::Speak?"]
    if clarification:
        (project[0] / "other.py").write_text("def Speak():\n    pass\n")
        inputs = ["Which functions call Speak?", "./voice.py::Speak"]
    replies = iter([*(SimpleNamespace(text=text, timed_out=False) for text in inputs),
                    SimpleNamespace(text="", timed_out=True)])
    monkeypatch.setattr(listener, "listen_for_speech_result", lambda: next(replies))
    original = router.process
    results = []
    monkeypatch.setattr(router, "process", lambda text: results.append(original(text, allow_interruption=False)))
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"))
    assert results[-1].success and results[-1].data["topic"]["qualified_name"] == "Speak"
    if clarification:
        assert not results[0].success and results[0].data["status"] == "ambiguous"
