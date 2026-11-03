"""C3.5b: real offline capability/receipt/voice lifecycle on disposable sources."""
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
import threading

import pytest

from commands import router
from services import project_access as access, capability_state, conversation_manager as conversation
from services import conversation_service as history, conversation_db
from services import scoped_relationship_delivery as delivery
from services import scoped_relationship_answer as construction
from services import project_relationship_capability as c2
from services.project_analysis_request import AnalysisLimits
from services.capability_executor import execute_capability
from services.cancellation import OperationCancelled
from services.tts.outcome import PlaybackOutcome
from services.conversation_speech import ConversationSpeech
from models.project_scope import CompletenessClaim


@pytest.fixture
def project(tmp_path, monkeypatch):
    previous = access._projects.copy(), access._active, access._revision
    old_history = list(history.conversation_history)
    old_delivery = history._active_delivery, history._delivery_generation
    history._active_delivery = None
    disabled = capability_state._DISABLED_CAPABILITIES.copy()
    access.register_project("FixtureC3", tmp_path)
    access.select_project("FixtureC3")
    capability_state._DISABLED_CAPABILITIES.discard("multi_file_reasoning")
    conversation.clear_topic()
    conversation.clear_pending_request()
    history.conversation_history.clear()
    heard, stops, callbacks, stored = [], [], [], []
    monkeypatch.setattr(history, "save_message", lambda role, text, source=None: stored.append((role, text, source)))
    monkeypatch.setattr(router, "add_message", history.add_message)
    monkeypatch.setattr(router, "speak", lambda text: heard.append(text) or PlaybackOutcome.COMPLETED)
    monkeypatch.setattr(router, "stop_speaking", lambda: stops.append(True))
    monkeypatch.setattr(router, "INTERRUPTION_HANDOFF_SECONDS", 0)

    def speech():
        return ConversationSpeech(speak_function=lambda text: heard.append(text) or PlaybackOutcome.COMPLETED,
                                  stop_function=lambda: stops.append(True))

    monkeypatch.setattr(router, "ConversationSpeech", speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda callback:
        callbacks.append(callback) or SimpleNamespace(start=lambda: None, stop=lambda: None))

    def forbidden(*a, **k):
        pytest.fail("C3 used a generic AI/agent/legacy analyzer fallback")

    for name in ("ask_ai", "detect_tool", "execute_agent", "refresh_project_analysis_if_changed"):
        monkeypatch.setattr(router, name, forbidden)

    def write(path, text):
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8", newline="\n")
        return file

    write("voice.py", "def Speak():\n    pass\n")
    write("app/run.py", "from voice import Speak as Say\ndef Run():\n    Say()\n")
    yield SimpleNamespace(root=tmp_path, write=write, heard=heard, stops=stops,
                          callbacks=callbacks, stored=stored, history=history.conversation_history)
    access._projects, access._active, access._revision = previous
    capability_state._DISABLED_CAPABILITIES = disabled
    history.conversation_history[:] = old_history
    history._active_delivery, history._delivery_generation = old_delivery
    conversation.clear_topic()
    conversation.clear_pending_request()


def args(command="Within app, what calls Speak?", **extra):
    return dict(context=access.get_project(), scoped_command=command, question=command, operation="calls", **extra)


@contextmanager
def owned(event=None):
    receipt = history.ResponseDelivery(event)
    try:
        with history.capture_response_delivery(receipt):
            yield receipt
    finally:
        if not receipt.closed:
            receipt.finish(PlaybackOutcome.UNKNOWN)


def produce(arguments, receipt):
    return next(router.stream_relationship_response(arguments, receipt.cancellation_event))


@pytest.mark.parametrize("command", ["Within app, what calls Speak?",
    "Which functions directly call Speak in file app/run.py?",
    "What functions call Speak in my FixtureC3 project?"])
def test_route_one_owner_and_complete_speech(project, monkeypatch, command):
    monkeypatch.setattr(c2, "analyze_project_relationships", lambda *a: pytest.fail("C2 also owned scoped query"))
    result = router.process(command, allow_interruption=False)
    assert result.success, result.error
    assert result.capability == "multi_file_reasoning"
    assert "Run" in project.heard[-1] and "Complete direct static" in project.heard[-1]
    assert "[" not in project.heard[-1] and "runtime execution" in project.heard[-1]
    assert len(project.heard) == 1
    assistant = [r for r in project.history if r["role"] == "assistant"]
    assert len(assistant) == 1 and assistant[0]["source"] == "observed"
    assert assistant[0]["playback_status"] == "completed"
    assert "[voice.py:" in assistant[0]["content"] and "_c3_publication" not in str(project.stored)


def test_project_scope_keeps_all_callers(project):
    project.write("outside.py", "from voice import Speak\ndef Outside():\n    Speak()\n")
    result = router.process("What calls Speak in my FixtureC3 project?", allow_interruption=False)
    assert result.success and "Outside" in result.data["response"] and "Run" in result.data["response"]
    assert "entire authorized project" in project.heard[-1]


@pytest.mark.parametrize("command", ["Which functions directly call Speak?", "Show callers of voice.py::Speak",
    "In this file, what calls Speak?"])
def test_missing_scope_or_current_file_clarifies_without_analysis(project, monkeypatch, command):
    monkeypatch.setattr(construction, "analyze_scoped_callers", lambda *a: pytest.fail("clarification analyzed callers"))
    result = router.process(command, allow_interruption=False)
    assert not result.success and result.data["status"] == "clarification"
    assert len(project.heard) == 1 and "Run" not in project.heard[-1]
    assert not any(r["source"] == "observed" for r in project.history)


def test_explicit_scope_clarification_reply_is_not_a_guess(project):
    assert not router.process("Which functions directly call Speak?", allow_interruption=False).success
    result = router.process("within app", allow_interruption=False)
    assert result.success and "Run" in result.data["response"]
    assert [r["content"] for r in project.history if r["role"] == "user"][-1] == "within app"


def test_target_clarification_reply_preserves_scope(project):
    project.write("app/other.py", "def Speak():\n    pass\n")
    first = router.process("Within app, what calls Speak?", allow_interruption=False)
    assert not first.success and first.data["status"] == "clarification"
    result = router.process("./voice.py::Speak", allow_interruption=False)
    assert result.success and 'directory "app"' in result.data["response"]


def test_explicit_file_reply_resolves_this_file_without_guessing(project):
    assert not router.process("In this file, what calls Speak?", allow_interruption=False).success
    result = router.process("in file app/run.py", allow_interruption=False)
    assert result.success and "Run" in result.data["response"]


def test_interrupted_scoped_queries_preserve_exact_case_and_paths(project):
    command = "Within app, show callers of voice.py::Speak"
    assert router.normalize_interruption("Wait, stop, " + command) == command
    result = router.process(router.INTERRUPTION_PREFIX + "Wait, stop, " + command, allow_interruption=False)
    assert "Run" in result


def test_verified_findings_only_speech_never_claims_completeness(project):
    project.write("app/run.py", "from voice import Speak\ndef Run(callback):\n    Speak()\n    callback()\n")
    result = router.process("Within app, show verified direct callers of Speak", allow_interruption=False)
    assert result.success, result.error
    assert result.data["status"] == "findings_only"
    assert "Additional callers may exist" in project.heard[-1]
    assert "Complete direct" not in project.heard[-1] and "Run" in project.heard[-1]


@pytest.mark.parametrize("dynamic", [False, True])
def test_empty_complete_and_incomplete_refusal(project, dynamic):
    project.write("app/run.py", "def Run(callback):\n    " + ("callback()" if dynamic else "pass") + "\n")
    result = router.process("Within app, what calls voice.py::Speak?", allow_interruption=False)
    assert result.success == (not dynamic)
    assert ("No direct static callers" in project.heard[-1]) == (not dynamic)
    if dynamic:
        assert not any(r["source"] == "observed" for r in project.history)


@pytest.mark.parametrize("change", ["source", "new_caller", "alternative", "revoke", "revision", "disable", "deadline"])
def test_queue_delivery_revalidates_before_any_fact_history(project, change):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        assert item.result.success and not project.history and not project.heard
        if change == "source":
            project.write("voice.py", "def Speak():\n    return 1\n")
        elif change == "new_caller":
            project.write("app/new.py", "from voice import Speak\nSpeak()\n")
        elif change == "alternative":
            project.write("voice/__init__.py", "def Speak():\n    pass\n")
        elif change == "revoke":
            access.revoke_project("FixtureC3")
        elif change == "revision":
            access.register_project("FixtureC3", project.root)
        elif change == "disable":
            capability_state._DISABLED_CAPABILITIES.add("multi_file_reasoning")
        else:
            item.result.data["_c3_publication"].request.budget._deadline = -1
        response = router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
        assert not item.result.success and "Run" not in response
        assert not any(r["source"] == "observed" for r in project.history)


@pytest.mark.parametrize("phase", ["analysis", "validated", "queued", "publication"])
def test_cancellation_discards_all_factual_effects(project, monkeypatch, phase):
    arguments = args()
    with owned() as receipt:
        if phase in {"analysis", "validated"}:
            name = "analyze_scoped_callers" if phase == "analysis" else "validate_scoped_callers"
            original = getattr(construction, name)

            def cancel(*a, **k):
                result = original(*a, **k)
                receipt.cancellation_event.set()
                return result

            monkeypatch.setattr(construction, name, cancel)
            with pytest.raises(OperationCancelled):
                produce(arguments, receipt)
        else:
            item = produce(arguments, receipt)
            if phase == "queued":
                receipt.cancellation_event.set()
            else:
                original = delivery.validate_scoped_callers

                def cancel(*a, **k):
                    receipt.cancellation_event.set()
                    return original(*a, **k)

                monkeypatch.setattr(delivery, "validate_scoped_callers", cancel)
            with pytest.raises(OperationCancelled):
                router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
    assert not project.history and not project.heard


@pytest.mark.parametrize("replacement", ["session", "boundary", "request"])
def test_session_or_request_replacement_discards_queued_answer(project, monkeypatch, replacement):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        if replacement == "session":
            monkeypatch.setattr(conversation_db, "current_session", SimpleNamespace(id=999))
        elif replacement == "boundary":
            history.clear_history()
        else:
            replacement_receipt = history.ResponseDelivery()
            replacement_receipt.activate()
        with pytest.raises(OperationCancelled):
            router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
    assert not project.history


def test_receipt_mismatch_and_replay_are_rejected(project):
    arguments = args()
    with owned() as first:
        item = produce(arguments, first)
        with owned() as second:
            with pytest.raises(OperationCancelled):
                router.present_relationship_result(item.result, arguments, second.cancellation_event)
    assert not project.history
    with owned() as receipt:
        item = produce(arguments, receipt)
        router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
        count = len(project.history)
        with pytest.raises(OperationCancelled):
            router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
        assert len(project.history) == count


def test_closed_receipt_cannot_be_reactivated(project):
    with owned() as receipt:
        produce(args(), receipt)
    with pytest.raises(OperationCancelled):
        with history.capture_response_delivery(receipt):
            pytest.fail("closed receipt replay admitted")


def test_new_static_command_also_supersedes_c3(project, monkeypatch):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        monkeypatch.setattr(router, "execute_registered_capability", lambda *a, **k: None)
        router.process("what time is it", allow_interruption=False)
        assert receipt.cancellation_event.is_set()
        with pytest.raises(OperationCancelled):
            router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
    assert not project.history


@pytest.mark.parametrize("tamper", ["question", "text", "scope"])
def test_mismatched_or_forged_delivery_is_not_published(project, tamper):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        handle = item.result.data["_c3_publication"]
        if tamper == "question":
            altered = {**arguments, "question": "different request"}
            with pytest.raises(OperationCancelled):
                router.present_relationship_result(item.result, altered, receipt.cancellation_event)
            assert not project.history
        else:
            if tamper == "text":
                item.result.data["_c3_publication"] = replace(handle, answer=replace(handle.answer, text="Forged caller facts"))
            else:
                item.result.data["_c3_publication"] = replace(handle, scope_id="forged")
            with pytest.raises(OperationCancelled):
                router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
            assert not project.history


def test_producer_cannot_claim_consumer_receipt(project):
    from contextvars import copy_context
    arguments = args()
    with owned() as receipt:
        context = copy_context()
        outcomes = []

        def worker():
            item = produce(arguments, receipt)
            try:
                router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
            except OperationCancelled:
                outcomes.append("rejected")

        thread = threading.Thread(target=lambda: context.run(worker))
        thread.start()
        thread.join(3)
        assert not thread.is_alive() and outcomes == ["rejected"]
    assert not project.history


def test_concurrent_request_cancels_old_producer_without_late_history(project):
    from contextvars import copy_context
    entered, release = threading.Event(), threading.Event()
    with owned() as receipt:
        context = copy_context()
        cancelled = []

        def worker():
            item = produce(args(), receipt)
            entered.set()
            assert release.wait(3)
            try:
                receipt.check_current()
            except OperationCancelled:
                cancelled.append(True)

        thread = threading.Thread(target=lambda: context.run(worker))
        thread.start()
        assert entered.wait(3)
        with owned():
            release.set()
            thread.join(3)
        assert not thread.is_alive() and cancelled == [True]
    assert not project.history


def test_actual_stream_and_speech_receipt_complete(project):
    response = router.process("Within app, what calls Speak?")
    assert "Run" in response and project.heard
    assert "Run" in " ".join(project.heard) and "[" not in " ".join(project.heard)
    rows = [r for r in project.history if r["role"] == "assistant"]
    assert len(rows) == 1 and rows[0]["playback_status"] == "completed"


@pytest.mark.parametrize("change", ["source", "session", "cancel", "deadline", "disable"])
def test_queued_speech_uses_existing_worker_guard(project, monkeypatch, change):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
        if change == "source":
            project.write("app/run.py", "from voice import Speak\ndef Changed():\n    Speak()\n")
        elif change == "session":
            monkeypatch.setattr(conversation_db, "current_session", SimpleNamespace(id=432))
        elif change == "cancel":
            receipt.cancellation_event.set()
        elif change == "deadline":
            item.result.data["_c3_publication"].request.budget._deadline = -1
        else:
            capability_state._DISABLED_CAPABILITIES.add("multi_file_reasoning")
        spoken = []
        speech = ConversationSpeech(speak_function=spoken.append, stop_function=lambda: None)
        speech.delivery_guard = receipt.playback_guard
        try:
            speech.add_chunk("Run directly calls Speak. More caller facts.")
            speech.finish()
            speech.speech_queue.join()
            assert not spoken and receipt.cancellation_event.is_set()
        finally:
            speech.stop()


def test_interruption_stops_factual_speech_and_marks_history(project, monkeypatch):
    spoken = []

    def speak(text):
        spoken.append(text)
        project.callbacks[0]("stop")
        return PlaybackOutcome.INTERRUPTED

    monkeypatch.setattr(router, "ConversationSpeech", lambda:
        ConversationSpeech(speak_function=speak, stop_function=lambda: project.stops.append(True)))
    # Avoid dispatching the handed-off control as a new request in this test.
    response = router.process_streaming_conversation("Within app, what calls Speak?",
        stream_factory=lambda event: router.stream_relationship_response(args(), event))
    assert response == router.INTERRUPTION_PREFIX + "stop" and len(spoken) == 1
    assert project.stops
    assert all(r["playback_status"] == "interrupted" for r in project.history if r["role"] == "assistant")


@pytest.mark.parametrize("change", ["session", "source", "deadline", "replacement"])
def test_mid_playback_changes_stop_remaining_sentences_and_stale_text(project, monkeypatch, change):
    spoken = []

    def speak(text):
        spoken.append(text)
        if change == "session":
            monkeypatch.setattr(conversation_db, "current_session", SimpleNamespace(id=1234))
        elif change == "source":
            project.write("voice.py", "def Speak():\n    return 1\n")
        elif change == "deadline":
            history._active_delivery.prepared_publication.request.budget._deadline = -1
        else:
            with owned():
                pass
        return PlaybackOutcome.COMPLETED

    monkeypatch.setattr(router, "ConversationSpeech", lambda:
        ConversationSpeech(speak_function=speak, stop_function=lambda: project.stops.append(True)))
    response = router.process_streaming_conversation("Within app, what calls Speak?",
        stream_factory=lambda event: router.stream_relationship_response(args(), event))
    assert response == "" and len(spoken) == 1
    assert project.stops
    assert all(r["playback_status"] == "interrupted" for r in project.history if r["role"] == "assistant")


def test_no_factual_streaming_before_validation(project, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = construction.validate_scoped_callers
    chunks = []

    def validate(*a, **k):
        entered.set()
        assert release.wait(3)
        return original(*a, **k)

    monkeypatch.setattr(construction, "validate_scoped_callers", validate)

    def consumer():
        with owned() as receipt:
            chunks.extend(router._stream_with_interrupt("question", SimpleNamespace(interrupted=receipt.cancellation_event),
                lambda event: router.stream_relationship_response(args(), event)))

    thread = threading.Thread(target=consumer)
    thread.start()
    assert entered.wait(3)
    assert not chunks and not project.history and not project.heard
    release.set()
    thread.join(4)
    assert not thread.is_alive() and chunks


def test_legacy_unscoped_and_transitive_c2_keep_their_owner(project, monkeypatch):
    calls = []
    original = c2.analyze_project_relationships
    monkeypatch.setattr(c2, "analyze_project_relationships", lambda r: calls.append(r) or original(r))
    assert router.process("What calls Speak?", allow_interruption=False).success
    assert router.process("Trace voice.py::Speak reverse", allow_interruption=False).success
    assert len(calls) == 2


def test_unsupported_caller_chains_do_not_use_generic_ai(project):
    result = router.process("Show caller chains of Speak within app", allow_interruption=False)
    assert not result.success and "reverse trace" in project.heard[-1]
    assert not any(r["source"] == "observed" for r in project.history)


def test_producer_without_receipt_cannot_emit_facts(project):
    result = execute_capability("multi_file_reasoning", args())
    assert not result.success and "receipt" in result.error
    assert not project.history and not project.heard


def test_already_cancelled_direct_capability_does_not_create_nested_receipts(project):
    event = threading.Event()
    event.set()
    with pytest.raises(OperationCancelled):
        router.execute_registered_capability("multi_file_reasoning", args(), cancellation_event=event)
    assert not project.history and not project.heard


@pytest.mark.parametrize("command", ["Go one level deeper", "What about its callers?", "Tell me more"])
def test_c3_followups_do_not_bypass_scope_via_generic_ai(project, command):
    assert router.process("Within app, what calls Speak?", allow_interruption=False).success
    result = router.process(command, allow_interruption=False)
    assert not result.success
    assert result.data["status"] in {"clarification", "not_applicable"}
    assert "Run" not in project.heard[-1]


@pytest.mark.parametrize("action", ["start", "end"])
def test_existing_session_boundaries_invalidate_c3_before_storage(project, monkeypatch, action):
    with owned() as receipt:
        produce(args(), receipt)
        stopped = []
        receipt.cancel_callback = lambda: stopped.append(True)
        monkeypatch.setattr(conversation_db, "current_session", None)

        def forbidden_storage():
            raise RuntimeError("fixture storage boundary")

        monkeypatch.setattr(conversation_db, "SessionLocal", forbidden_storage)
        if action == "start":
            with pytest.raises(RuntimeError, match="fixture storage boundary"):
                conversation_db.start_session()
        else:
            conversation_db.end_session()
        assert receipt.cancellation_event.is_set() and stopped == [True]


def test_result_dictionary_cannot_inject_alternate_history_or_topic(project):
    arguments = args()
    with owned() as receipt:
        item = produce(arguments, receipt)
        item.result.data["response"] = "Forged relationship facts"
        item.result.data["topic"] = {"type": "project", "relationship_grounded": True, "filename": "invented.py"}
        response = router.present_relationship_result(item.result, arguments, receipt.cancellation_event)
        assert "Forged" not in response
        assert conversation.get_topic()["filename"] == "./voice.py"
        assert not any("Forged" in r["content"] for r in project.history)


def test_invalid_target_clarification_never_falls_back_to_ai(project):
    project.write("app/other.py", "def Speak():\n    pass\n")
    assert not router.process("Within app, what calls Speak?", allow_interruption=False).success
    result = router.process("voice.py::speak", allow_interruption=False)
    assert not result.success and result.data["status"] == "clarification"
    assert "Run" not in project.heard[-1]
