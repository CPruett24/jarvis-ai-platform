"""Refusal metadata must not become source facts or disclose private diagnostic text."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from commands import router
from services import project_access as access
from services.project_analysis_request import AnalysisLimits, AnalysisRequest
from services.project_analysis_index import analyze_project_relationships
from services.project_graph import build_relationship_graph, traverse_relationships
from services.project_relationship_answer import answer_relationships, _incomplete_response
from models.project_relationships import RelationshipKind
from services.capability_executor import CapabilityExecutionResult
from services.tts.outcome import PlaybackOutcome
from test_c2_capability_routing import project

_streaming_conversation = router.process_streaming_conversation


def analyze(limits=None, depth=2):
    request = AnalysisRequest.capture(limits=limits, clock=lambda: 0)
    analysis = analyze_project_relationships(request)
    graph = build_relationship_graph(analysis, request, RelationshipKind.CALLS)
    trace = traverse_relationships(graph, request, qualified_name="SaveHistory", direction="reverse", max_depth=depth)
    return analysis, graph, trace, request


@pytest.mark.parametrize("mode,expected", [
    ("unsupported", "unsupported source coverage"),
    ("relationships", "relationship extraction limit reached"),
    ("depth", "traversal depth limit reached"),
    ("edges", "traversal edge limit reached"),
    ("boundaries", "unresolved relationship boundaries"),
    ("parse", "source parsing failures"),
])
def test_actual_metadata_drives_each_category(project, mode, expected):
    limits, depth = None, 2
    if mode == "unsupported":
        project.write("private_notes.md", "DO NOT DISCLOSE THIS CONTENT\n")
    elif mode == "relationships":
        limits = replace(AnalysisLimits(), relationships=1)
    elif mode == "depth":
        depth = 1
    elif mode == "edges":
        limits = replace(AnalysisLimits(), traversed_edges=1)
    elif mode == "boundaries":
        project.write("dynamic.py", "def dynamic(callback):\n    callback()\n")
    else:
        project.write("broken.py", "def PRIVATE_ERROR(:\n")
    analysis, graph, trace, request = analyze(limits, depth)
    answer = answer_relationships(analysis, trace, request)
    assert not answer.success and answer.status == "incomplete"
    assert expected in answer.text and "No relationship facts were published" in answer.text
    for forbidden in ("DO NOT DISCLOSE", "private_notes", "PRIVATE_ERROR", "callback", "Confirmed static", "[", "SaveHistory"):
        assert forbidden not in answer.text


def test_multiple_reasons_are_deterministic_and_do_not_invent_counts(project):
    project.write("notes.md", "private\n")
    project.write("dynamic.py", "def dynamic(callback):\n    callback()\n")
    analysis, graph, trace, request = analyze(depth=1)
    answer = answer_relationships(analysis, trace, request)
    assert answer.text == (
        "The relationship analysis is incomplete. Reasons: unsupported source coverage; "
        "traversal depth limit reached; unresolved relationship boundaries. No relationship facts were published.")
    assert "edge limit" not in answer.text and "extraction limit" not in answer.text
    assert not any(character.isdigit() for character in answer.text)


def test_metadata_absence_and_unknown_reason_never_invent_details(project):
    analysis, graph, trace, _ = analyze()
    # Exercise presentation alone with no explanatory metadata. No forged result
    # is passed through publication; unknown strings must never be echoed.
    unknown = replace(trace, cutoff_reasons=("PRIVATE_UNRECOGNIZED_REASON",))
    text = _incomplete_response(analysis, graph, unknown)
    assert "Detailed refusal metadata is unavailable" in text
    assert "PRIVATE" not in text and "limit reached" not in text


def test_incomplete_coverage_without_detailed_metadata_has_safe_fallback(project):
    analysis, _, _, request = analyze()
    coverage = analysis.snapshot.coverage
    # A discovered but unaccounted entry makes completeness false even when
    # there is no specific skipped/unsupported/budget diagnostic to display.
    coverage = replace(coverage, discovered=coverage.discovered + ("PRIVATE_UNACCOUNTED.py",))
    analysis = replace(analysis, snapshot=replace(analysis.snapshot, coverage=coverage))
    graph = build_relationship_graph(analysis, request, RelationshipKind.CALLS)
    answer = answer_relationships(analysis, graph, request)
    assert not answer.success and answer.status == "incomplete"
    assert "Detailed refusal metadata is unavailable" in answer.text
    assert "PRIVATE" not in answer.text and "limit reached" not in answer.text


def test_unauthorized_analysis_cannot_disclose_diagnostic_categories(project):
    project.write("sensitive_notes.md", "private source\n")
    analysis, _, trace, request = analyze()
    access.revoke_project("fixture")
    answer = answer_relationships(analysis, trace, request)
    assert not answer.success
    assert "unsupported source coverage" not in answer.text and "sensitive" not in answer.text


def test_capability_contract_and_actual_router_refusal(project):
    project.write("notes.md", "private\n")
    result = router.process("What functions call SaveHistory?", allow_interruption=False)
    assert isinstance(result, CapabilityExecutionResult)
    assert not result.success and result.capability == "multi_file_reasoning"
    assert result.data["status"] == "incomplete"
    assert "unsupported source coverage" in result.error
    assert "unsupported source coverage" in project.heard[-1]
    assert not any(source == "observed" for _, _, source in project.saved)


def test_successful_answers_unchanged(project):
    first = router.process("What calls SaveHistory?", allow_interruption=False)
    second = router.process("What calls SaveHistory?", allow_interruption=False)
    assert first.success and second.success
    assert first.data["response"] == second.data["response"]
    assert "Confirmed static call" in first.data["response"]
    assert "Reasons:" not in first.data["response"]


@pytest.mark.parametrize("capability", [True, False])
def test_streaming_log_distinguishes_delivery_source(project, monkeypatch, capsys, capability):
    # Real shared lifecycle, fake speech and capture; no hardware is started.
    speech = SimpleNamespace(start_response=lambda: None, add_chunk=lambda text: None,
        finish=lambda: None, is_finished=lambda: True, interrupt=lambda: None,
        stop=lambda: None, playback_outcome=lambda: PlaybackOutcome.COMPLETED)
    monkeypatch.setattr(router, "ConversationSpeech", lambda: speech)
    monkeypatch.setattr(router, "SpeechInterruptMonitor", lambda cb:
        SimpleNamespace(start=lambda: None, stop=lambda: None))
    def stream(*a, **k):
        yield "A fixture response."
    monkeypatch.setattr(router, "stream_ai_response", stream)
    _streaming_conversation("fixture", stream_factory=stream if capability else None)
    output = capsys.readouterr().out
    assert ("Streaming capability response..." in output) == capability
    assert ("Calling streaming conversation AI..." in output) == (not capability)
