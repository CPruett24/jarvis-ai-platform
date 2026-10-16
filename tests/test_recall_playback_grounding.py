"""No audio/network; all persistence uses disposable SQLite or the safe runner."""
import json
import threading
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from commands import router
from models import database
from models.conversation import Conversation
from models.session import Session
from services import conversation_db as archive, conversation_service as history
from services import historical_recall as recall
from services.conversation_speech import ConversationSpeech
from services.tts.outcome import PlaybackOutcome as Outcome
from services.speaker import InterruptibleSpeaker
from services.tts.fallback_provider import FallbackTTSProvider


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(archive, "SessionLocal", factory)
    monkeypatch.setattr(archive, "current_session", SimpleNamespace(id=1))
    monkeypatch.setattr(history, "save_message", archive.save_message)
    history.clear_history()
    with factory() as session:
        session.add(Session(id=1))
        session.commit()
    yield factory
    history.clear_history()
    engine.dispose()


def test_additive_migration_is_idempotent_and_legacy_unknown(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE conversations (id INTEGER PRIMARY KEY, message VARCHAR)"))
        connection.execute(text("INSERT INTO conversations VALUES (1, 'legacy generated text')"))
    monkeypatch.setattr(database, "engine", engine)
    database.ensure_conversation_playback_column()
    database.ensure_conversation_playback_column()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT playback_status, message FROM conversations")).one() == (
            "unknown", "legacy generated text")
    assert len(inspect(engine).get_columns("conversations")) == 3
    engine.dispose()


@pytest.mark.parametrize("source", ["ollama", "historical_recall"])
@pytest.mark.parametrize("status", [Outcome.COMPLETED, Outcome.INTERRUPTED, Outcome.TIMED_OUT,
                                    Outcome.FAILED, Outcome.UNKNOWN])
def test_operation_receipt_preserves_full_generated_text(db, source, status):
    receipt = history.ResponseDelivery()
    full = "Generated response. " * 100
    with history.capture_response_delivery(receipt):
        history.add_message("assistant", full, source=source)
    receipt.finish(status)
    with db() as session:
        row = session.query(Conversation).one()
        assert (row.message, row.source, row.playback_status) == (full, source, status.value)


def test_late_save_uses_its_own_receipt(db):
    first, second = history.ResponseDelivery(), history.ResponseDelivery()
    first.finish(Outcome.INTERRUPTED)
    with history.capture_response_delivery(second):
        history.add_message("assistant", "second", source="ollama")
    second.finish(Outcome.COMPLETED)
    with history.capture_response_delivery(first):
        history.add_message("assistant", "late first", source="ollama")
    with db() as session:
        assert [(row.message, row.playback_status) for row in session.query(Conversation).order_by(Conversation.id)] == [
            ("second", "completed"), ("late first", "interrupted")]


@pytest.mark.parametrize("source", ["ollama", "historical_recall"])
@pytest.mark.parametrize("status", [Outcome.COMPLETED, Outcome.INTERRUPTED, Outcome.TIMED_OUT])
def test_router_propagates_post_generation_playback_status(db, monkeypatch, source, status):
    callback = []
    full = "Full generated answer. " * 10
    def stream(*args, **kwargs):
        yield full
        history.add_message("assistant", full, source=source)
    def finished():
        if status == Outcome.INTERRUPTED:
            callback[0]("That's all")
        return status == Outcome.COMPLETED
    speech = SimpleNamespace(start_response=lambda: None, add_chunk=lambda _: None,
        finish=lambda: None, is_finished=finished, interrupt=lambda: None,
        stop=lambda: None, playback_outcome=lambda: status)
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: callback.append(cb) or
                        SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(router, "stream_ai_response", stream)
    monkeypatch.setattr(router, "PLAYBACK_INACTIVITY_SECONDS", 0.01)
    monkeypatch.setattr(router, "INTERRUPTION_HANDOFF_SECONDS", 0)
    answer = router.process_streaming_conversation("question")
    assert (answer.startswith(router.INTERRUPTION_PREFIX)) == (status == Outcome.INTERRUPTED)
    with db() as session:
        row = session.query(Conversation).one()
        assert (row.message, row.source, row.playback_status) == (full, source, status.value)


def test_nonstreaming_uses_same_receipt(db, monkeypatch):
    def ask(_):
        history.add_message("assistant", "generated recap", source="historical_recall")
        return "generated recap"
    monkeypatch.setattr(router, "ask_ai", ask)
    monkeypatch.setattr(router, "speak", lambda _: Outcome.COMPLETED)
    assert router._ask_and_speak("request") == "generated recap"
    with db() as session:
        assert session.query(Conversation).one().playback_status == "completed"


@pytest.mark.parametrize("result", [Outcome.COMPLETED, Outcome.FAILED, Outcome.SKIPPED, Outcome.INTERRUPTED, None])
def test_only_explicit_success_updates_progress(result):
    speech = ConversationSpeech(speak_function=lambda _: result, stop_function=lambda: None)
    try:
        speech.add_chunk("Inheritance works. ")
        speech.finish()
        assert speech.wait_until_finished(1)
        assert (speech.last_success_at is not None) == (result == Outcome.COMPLETED)
        if result == Outcome.SKIPPED:
            assert speech.playback_outcome() == Outcome.FAILED
    finally:
        speech.stop()


@pytest.mark.parametrize("result", [Outcome.COMPLETED, Outcome.INTERRUPTED, Outcome.TIMED_OUT,
                                    Outcome.FAILED, Outcome.SKIPPED, None])
def test_provider_outcome_reaches_speaker_through_fallback(result):
    provider = SimpleNamespace(speak=lambda _: result, stop=lambda: None)
    fallback = FallbackTTSProvider(provider, provider)
    speaker = InterruptibleSpeaker(fallback)
    assert speaker.speak("A sentence.") == (Outcome.UNKNOWN if result is None else result)


def test_failed_later_utterance_keeps_last_success_timestamp():
    responses = iter([Outcome.COMPLETED, Outcome.FAILED])
    speech = ConversationSpeech(speak_function=lambda _: next(responses), stop_function=lambda: None)
    try:
        speech.add_chunk("First sentence. ")
        assert speech.wait_until_finished(1)
        successful = speech.last_success_at
        speech.add_chunk("Failed sentence. ")
        speech.finish()
        assert speech.wait_until_finished(1)
        assert successful is not None and speech.last_success_at == successful
        assert speech.playback_outcome() == Outcome.FAILED
    finally:
        speech.stop()


def test_blocked_worker_cleanup_is_bounded():
    release, entered = threading.Event(), threading.Event()
    def blocked(_):
        entered.set()
        release.wait(2)
        return Outcome.COMPLETED
    speech = ConversationSpeech(speak_function=blocked, stop_function=lambda: None)
    speech.add_chunk("A blocked sentence. ")
    speech.finish()
    assert entered.wait(1)
    try:
        speech.mark_timeout()
        assert speech.stop(timeout=0.01) is False
        assert speech.playback_outcome() == Outcome.TIMED_OUT
    finally:
        release.set()
        speech.worker.join(1)
    assert speech.last_success_at is None


@pytest.mark.parametrize("healthy", [True, False])
def test_router_inactivity_watchdog_with_virtual_long_response(monkeypatch, healthy):
    clock = [0.0]
    progress = [None]
    events = []
    def finished():
        clock[0] += 20
        if healthy:
            progress[0] = clock[0]
        return clock[0] >= 200 if healthy else False
    speech = SimpleNamespace(start_response=lambda: None, add_chunk=lambda _: None,
        finish=lambda: None, is_finished=finished, progress_timestamp=lambda: progress[0],
        interrupt=lambda: events.append("interrupt"), mark_timeout=lambda: events.append("timeout"),
        stop=lambda: events.append("closed"), playback_outcome=lambda: Outcome.COMPLETED)
    monkeypatch.setattr(router, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda _: None))
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda _: SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(router, "_stream_with_interrupt", lambda *a: iter(["full response"]))
    assert router.process_streaming_conversation("question") == "full response"
    assert ("timeout" in events) == (not healthy)
    assert clock[0] >= (200 if healthy else 120)


def test_topic_pairs_are_adjacent_chronological_and_recap_barriers(db):
    rows = [
        ("user", "Explain REST", "user"),
        ("assistant", "REST uses HTTP", "ollama"),
        ("user", "Explain inheritance", "user"),
        ("assistant", "Inheritance reuses parent behavior.", "ollama"),
        ("user", "Explain inheritance again", "user"),
        ("user", "Explain Python", "user"),
        ("assistant", "Python is a language", "ollama"),
        ("assistant", "Inheritance recap", "historical_recall"),
        ("user", "Inheritance?", "user"),
        ("assistant", "Inheritance recap", "historical_recall"),
        ("assistant", "not a corresponding answer", "ollama"),
    ]
    with db() as session:
        for n, (role, message, source) in enumerate(rows, 1):
            session.add(Conversation(id=n, session_id=1, role=role, message=message,
                                     source=source, timestamp=datetime(2026, 10, 10)))
        session.commit()
    selection = archive.get_historical_messages(cutoff=11, topic="inheritance")
    assert [row["id"] for row in selection.records] == [3, 4, 5, 9]
    assert [row.get("answer_id") for row in selection.records if row["role"] == "user"] == [4, None, None]
    evidence, _ = recall.format_evidence(selection)
    presentation = recall.build_grounded_recap('I fully explained Python and REST. Next step!', evidence,
                                               recall.RecallDecision("summarize", "inheritance"))
    answer = presentation.text
    assert "Python" not in answer and "REST" not in answer and "Next step" not in answer
    assert "don't have a saved answer" in answer
    assert answer.index("saved explanation") < answer.index("Later, you asked")
    assert {anchor["id"] for anchor in presentation.anchors} == {3, 4, 9}
    assert "message" not in answer


def evidence_row(n, content, **extra):
    return dict(id=n, session_id=1, timestamp=datetime(2026, 10, 10), role="assistant",
                source="ollama", content=content, playback_status="unknown", **extra)


def test_budget_prioritizes_direct_and_preserves_order(monkeypatch):
    records = [evidence_row(1, "Python " * 100, relevance="context"),
               evidence_row(2, "Inheritance reuses behavior.", relevance="direct")]
    monkeypatch.setattr(recall, "MAX_EVIDENCE_CHARS", 400)
    evidence, partial = recall.format_evidence(archive.HistoricalSelection(records))
    assert partial and [json.loads(line)["id"] for line in evidence.splitlines()] == [2]


@pytest.mark.parametrize("operation", ["summarize", "continue"])
def test_validated_excerpts_control_attribution_and_continuation(operation):
    evidence, _ = recall.format_evidence(archive.HistoricalSelection([
        evidence_row(1, "Inheritance reuses behavior.", relevance="direct"),
        evidence_row(2, "Python is a language.", relevance="context")]))
    # A context anchor and made-up quote must not validate a substantive claim.
    malicious = json.dumps({"excerpts": [{"id": 2, "quote": "Python is a language."},
                                         {"id": 1, "quote": "I fully explained inheritance."}]})
    presentation = recall.build_grounded_recap(malicious, evidence, recall.RecallDecision(operation, "inheritance"))
    answer = presentation.text
    assert "can't confirm how much" not in answer and "can't reliably summarize" not in answer
    assert not presentation.model_selection_valid
    assert [anchor["id"] for anchor in presentation.anchors] == [1]
    assert "Python" not in answer and "fully explained" not in answer
    assert "message" not in answer and "unknown" not in answer
    assert ("Would you like" in answer) == (operation == "continue")
    if operation == "continue":
        assert len(answer.split()) < 20


def test_valid_model_excerpts_keep_chronology_and_recorded_delivery():
    rows = [evidence_row(1, "Inheritance reuses behavior.", relevance="direct"),
            evidence_row(2, "Inheritance has types.", relevance="direct")]
    rows[0]["playback_status"] = "completed"
    rows[1]["playback_status"] = "interrupted"
    evidence, _ = recall.format_evidence(archive.HistoricalSelection(rows))
    raw = json.dumps({"excerpts": [{"id": row["id"], "quote": row["content"]} for row in reversed(rows)]})
    presentation = recall.build_grounded_recap(raw, evidence, recall.RecallDecision("summarize", "inheritance"))
    answer = presentation.text
    # Topic summaries use the latest saved explanation; anchors carry delivery.
    assert [anchor["id"] for anchor in presentation.anchors] == [2]
    assert presentation.anchors[0]["playback_status"] == "interrupted"
    assert "can't confirm how much" not in answer and "has types" in answer
    assert "Would you like" not in answer


@pytest.mark.parametrize("outcome", [Outcome.FAILED, Outcome.UNKNOWN, Outcome.COMPLETED, Outcome.TIMED_OUT])
@pytest.mark.parametrize("phase", ["close", "monitor", None])
def test_final_status_after_bounded_monitor_drain(db, monkeypatch, outcome, phase):
    callbacks, events = [], []
    def stream(*a, **k):
        yield "Saved answer."
        history.add_message("assistant", "Saved answer.", source="ollama")
    def close():
        events.append("close")
        if phase == "close":
            callbacks[0]("That's all")
    def stop_monitor():
        events.append("monitor")
        if phase == "monitor":
            callbacks[0]("That's all")
    speech = SimpleNamespace(start_response=lambda: None, add_chunk=lambda _: None,
        finish=lambda: None, is_finished=lambda: True, interrupt=lambda: None,
        stop=close, playback_outcome=lambda: outcome)
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: callbacks.append(cb) or
                        SimpleNamespace(start=lambda: None, stop=stop_monitor))
    monkeypatch.setattr(router, "stream_ai_response", stream)
    monkeypatch.setattr(history, "voice_trace", lambda event, **fields: events.append((event, fields)))
    result = router.process_streaming_conversation("question")
    expected = Outcome.INTERRUPTED if phase and outcome != Outcome.TIMED_OUT else outcome
    assert result.startswith(router.INTERRUPTION_PREFIX) == bool(phase)
    with db() as session:
        row = session.query(Conversation).one()
        assert row.playback_status == expected.value and row.message == "Saved answer."
    assert events[:2] == ["close", "monitor"]
    assert events[2][0] == "playback_final" and events[2][1]["outcome"] == expected.value
    callbacks[0]("late command after handoff")  # Closed window cannot change the result.
    with db() as session:
        assert session.query(Conversation).one().playback_status == expected.value


def test_real_response_exception_is_not_reclassified_by_cleanup_interrupt(db, monkeypatch):
    callbacks, results = [], []
    def broken_stream(*a):
        history.add_message("assistant", "Saved before response failure", source="ollama")
        raise RuntimeError("Response failure")
        yield
    speech = SimpleNamespace(start_response=lambda: None, interrupt=lambda: None, stop=lambda: None)
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: callbacks.append(cb) or
        SimpleNamespace(start=lambda: None, stop=lambda: callbacks[0]("That's all")))
    monkeypatch.setattr(router, "_stream_with_interrupt", broken_stream)
    monkeypatch.setattr(history, "voice_trace", lambda event, **fields: results.append(fields))
    with pytest.raises(RuntimeError, match="Response failure"):
        router.process_streaming_conversation("question")
    assert results[-1]["outcome"] == "failed"
    with db() as session:
        assert session.query(Conversation).one().playback_status == "failed"


def test_intentional_end_retains_interrupted_status_with_late_active_worker(db, monkeypatch):
    from services import conversation_speech as speech_module
    entered, release = threading.Event(), threading.Event()
    callbacks, events, workers = [], [], []
    def speak(_):
        entered.set()
        assert release.wait(2)
        return Outcome.COMPLETED
    def speech_factory():
        speech = ConversationSpeech(speak_function=speak, stop_function=lambda: None)
        workers.append(speech)
        return speech
    def stream(*a):
        yield "Active sentence. Waiting sentence."
        assert entered.wait(1)
        history.add_message("assistant", "Active sentence. Waiting sentence.", source="ollama")
        callbacks[0]("That's all")
    def trace(event, **fields):
        events.append((event, fields))
        if event == "playback_final":
            assert fields["outcome"] == "interrupted"
            release.set()  # The active provider acknowledges only after finalization.
    monkeypatch.setattr(router, "ConversationSpeech", speech_factory)
    monkeypatch.setattr(router, "_stream_with_interrupt", stream)
    monkeypatch.setattr(router, "INTERRUPTION_HANDOFF_SECONDS", 0)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb: callbacks.append(cb) or
                        SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(history, "voice_trace", trace)
    monkeypatch.setattr(speech_module, "voice_trace", trace)
    try:
        result = router.process_streaming_conversation("question")
        assert result == router.INTERRUPTION_PREFIX + "That's all"
        workers[0].worker.join(1)
        assert not workers[0].worker.is_alive()
        assert any(event == "utterance_result" and fields["outcome"] == "skipped" for event, fields in events)
        final_index = next(i for i, (event, _) in enumerate(events) if event == "playback_final")
        active_index = next(i for i, (event, fields) in enumerate(events)
                            if event == "utterance_result" and fields["outcome"] == "interrupted")
        assert final_index < active_index
        with db() as session:
            row = session.query(Conversation).one()
            assert row.playback_status == "interrupted" and "Waiting sentence" in row.message
    finally:
        release.set()
        for speech in workers:
            speech.stop()
