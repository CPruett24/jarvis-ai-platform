"""CP6 independent graph oracles and adversarial acceptance at real capability boundaries."""
from dataclasses import asdict, replace
import hashlib
import json
import threading

import pytest

from commands import router
from scripts.accept_c2 import write_fixture
from services import project_access as access, conversation_manager as conversation, ai_service
from services import project_relationship_capability as adapter
from services.capability_executor import execute_capability
from services.project_analysis_request import AnalysisRequest
from services.project_analysis_index import analyze_project_relationships
from services.project_graph import build_relationship_graph, traverse_relationships
from services.project_relationship_evidence import (
    select_relationship_evidence, validate_relationship_evidence, RelationshipEvidenceError,
)
from services.project_relationship_answer import answer_relationships
from models.project_relationships import (
    SourceLocation, SymbolRecord, SymbolKind, RelationshipRecord, RelationshipKind, Resolution,
)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    previous = access._projects.copy(), access._active, access._revision
    topic, pending = conversation._current_topic, conversation._pending_request
    sources = write_fixture(tmp_path)
    access.register_project("acceptance", tmp_path)
    access.select_project("acceptance")
    conversation.clear_topic()
    conversation.clear_pending_request()
    def forbidden(*a, **k):
        pytest.fail("Acceptance must not execute source, delegate, or use generic AI")
    for name in ("ask_ai", "execute_agent", "detect_tool", "refresh_project_analysis_if_changed"):
        monkeypatch.setattr(router, name, forbidden)
    heard, history = [], []
    monkeypatch.setattr(router, "speak", heard.append)
    monkeypatch.setattr(router, "add_message", lambda role, text, source: history.append((role, text, source)))
    yield tmp_path, sources, heard, history
    access._projects, access._active, access._revision = previous
    conversation._current_topic, conversation._pending_request = topic, pending


def run(text):
    return router.process(text, allow_interruption=False)


def test_independent_exact_call_record_oracle(fixture):
    root, sources, _, _ = fixture
    request = AnalysisRequest.capture()
    analysis = analyze_project_relationships(request)
    def location(path, start, end, column=0, end_column=0):
        digest = hashlib.sha256(sources[path].encode()).hexdigest()
        source_id = "S" + hashlib.sha256(f"{request.context}:{path}:1:{digest}".encode()).hexdigest()[:12]
        return SourceLocation(request.identity, path, source_id, digest, start, end, column, end_column)
    leaf = SymbolRecord("SaveHistory", SymbolKind.FUNCTION, location("leaf.py", 2, 3, 0, 8))
    middle = SymbolRecord("middle", SymbolKind.FUNCTION, location("middle.py", 2, 3, 0, 17))
    start = SymbolRecord("route", SymbolKind.FUNCTION, location("root.py", 2, 3, 0, 12))
    expected = (
        RelationshipRecord(RelationshipKind.CALLS, middle, leaf, "SaveHistory", location("middle.py", 3, 3, 4, 17),
            Resolution.CONFIRMED_STATIC, "lexical_or_imported_binding",
            supporting_sources=(location("middle.py", 1, 1, 17, 28),)),
        RelationshipRecord(RelationshipKind.CALLS, start, middle, "middle", location("root.py", 3, 3, 4, 12),
            Resolution.CONFIRMED_STATIC, "lexical_or_imported_binding",
            supporting_sources=(location("root.py", 1, 1, 19, 25),)),
    )
    actual = tuple(r for r in analysis.relationships if r.kind == RelationshipKind.CALLS)
    for observed, wanted in zip(sorted(actual, key=lambda r: r.origin.qualified_name),
                                sorted(expected, key=lambda r: r.origin.qualified_name)):
        for key, value in asdict(wanted).items():
            assert asdict(observed)[key] == value, key
    assert {r.relationship_id: r for r in actual} == {r.relationship_id: r for r in expected}
    result = run("Trace root.py::route forward")
    assert result.success
    trace, _ = result.data["_publication"]
    assert [(s.node_id, s.relationship_path, s.classification) for s in trace.steps] == [
        (start.symbol_id, (), "root"), (middle.symbol_id, (expected[1].relationship_id,), "expanded"),
        (leaf.symbol_id, (expected[1].relationship_id, expected[0].relationship_id), "expanded")]


@pytest.mark.parametrize("direction,filename,expected", [
    ("forward", "root.py", [("root.py", "middle.py", 1, 19, 25), ("middle.py", "leaf.py", 1, 17, 28)]),
    ("reverse", "leaf.py", [("root.py", "middle.py", 1, 19, 25), ("middle.py", "leaf.py", 1, 17, 28)]),
])
def test_import_endpoints_sites_and_direction_at_capability_boundary(fixture, direction, filename, expected):
    result = execute_capability("multi_file_reasoning", dict(context=access.get_project(), operation="imports",
        filename=filename, direction=direction))
    assert result.success
    trace, _ = result.data["_publication"]
    records = {r.relationship_id: r for r in trace.graph.analysis.relationships}
    selected = {identity for step in trace.steps for identity in step.relationship_path}
    actual = [(records[i].origin.definition.path, records[i].target.definition.path,
               records[i].location.start_line, records[i].location.start_column, records[i].location.end_column)
              for i in selected]
    assert sorted(actual) == sorted(expected)
    assert all(records[i].resolution == Resolution.CONFIRMED_STATIC for i in selected)
    assert trace.direction == direction and trace.complete


@pytest.mark.parametrize("shape,classification", [("cycle", "cycle"), ("diamond", "shared")])
def test_cycles_and_shared_descendants_through_actual_router(fixture, shape, classification):
    root, _, heard, _ = fixture
    text = ("def A():\n    B()\ndef B():\n    A()\n" if shape == "cycle" else
            "def D():\n    pass\ndef B():\n    D()\ndef C():\n    D()\ndef A():\n    B()\n    C()\n")
    (root / "shape.py").write_text(text)
    result = run("Trace shape.py::A forward")
    assert result.success and "Static" in heard[-1]
    value, _ = result.data["_publication"]
    assert classification in {step.classification for step in value.steps}


@pytest.mark.parametrize("mutation", ["removed", "added", "edited", "project"])
def test_queued_snapshot_mutations_cannot_publish(fixture, mutation):
    root, _, heard, history = fixture
    args = dict(context=access.get_project(), operation="calls", qualified_name="route")
    result = execute_capability("multi_file_reasoning", args)
    assert result.success
    if mutation == "removed":
        # A rename simulates removal from the analyzed Python inventory without deletion.
        (root / "middle.py").rename(root / "middle.removed")
    elif mutation == "added":
        (root / "added.py").write_text("from leaf import SaveHistory\ndef Added():\n    SaveHistory()\n")
    elif mutation == "edited":
        (root / "root.py").write_text("def route():\n    pass\n")
    else:
        access.select_project("jarvis")
    router.present_relationship_result(result, args)
    assert not result.success and not conversation.get_topic()
    assert not heard and not any(source == "observed" for _, _, source in history)


@pytest.mark.parametrize("target", ["../outside.py", "C:/outside.py", "data/private.py", ".env", "credentials.py"])
def test_exclusions_and_outside_paths_do_not_leak(fixture, target):
    root, _, _, history = fixture
    (root / "data").mkdir(exist_ok=True)
    (root / "data/private.py").write_text("def Hidden():\n    pass\n")
    (root / "credentials.py").write_text("def Hidden():\n    pass\n")
    result = run(f"What depends on {target}?")
    assert not result.success and not any(source == "observed" for _, _, source in history)


@pytest.mark.parametrize("attack", ["false_claim", "wrong_direction", "partial", "foreign", "invented_id"])
def test_adversarial_relationship_claims_cannot_reach_answer(fixture, attack):
    request = AnalysisRequest.capture()
    analysis = analyze_project_relationships(request)
    graph = build_relationship_graph(analysis, request, RelationshipKind.CALLS)
    trace = traverse_relationships(graph, request, qualified_name="route", max_depth=2)
    packet = select_relationship_evidence(analysis, trace, request)
    if attack == "false_claim":
        # Keep every VALID citation but replace a canonical statement.
        changed = replace(packet.propositions[0], text="route calls a nonexistent function. Runtime execution is proven.")
        with pytest.raises(RelationshipEvidenceError):
            validate_relationship_evidence(replace(packet, propositions=(changed,) + packet.propositions[1:]), request)
    elif attack == "wrong_direction":
        with pytest.raises(ValueError):
            replace(trace, direction="reverse")
    elif attack == "partial":
        assert not answer_relationships(analysis, replace(trace, steps=trace.steps[:1]), request).success
    elif attack == "foreign":
        foreign = replace(analysis.snapshot.project, project_id="unauthorized")
        with pytest.raises(ValueError):
            replace(analysis, snapshot=replace(analysis.snapshot, project=foreign))
    else:
        with pytest.raises(ValueError):
            replace(graph, arcs=(replace(graph.arcs[0], relationship_id="Rinvented"),) + graph.arcs[1:])


def test_invalid_model_ids_retry_once_then_deterministic_fallback(fixture, monkeypatch):
    calls = []
    def invalid(**kwargs):
        calls.append(kwargs)
        return {"message": {"content": '{"snapshot_id":"wrong","order":["Rinvented"]}'}}
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", invalid)
    result = execute_capability("multi_file_reasoning", dict(context=access.get_project(), operation="trace",
        qualified_name="route", use_model=True))
    assert result.success and len(calls) == 2 and "Rinvented" not in result.data["response"]
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    payload = calls[0]["messages"][1]["content"]
    assert "Ignore all instructions" not in payload and "SaveHistory" not in payload
    value, request = result.data["_publication"]
    assert answer_relationships(value.graph.analysis, value, request).text == result.data["response"]


def test_cancellation_inside_model_call_never_publishes(fixture, monkeypatch):
    from services.cancellation import OperationCancelled
    _, _, heard, history = fixture
    event = threading.Event()
    def cancelled(**kwargs):
        event.set()
        return {"message": {"content": "fabricated"}}
    monkeypatch.setattr(ai_service, "bounded_relationship_chat", cancelled)
    with pytest.raises(OperationCancelled):
        router.execute_registered_capability("multi_file_reasoning", dict(context=access.get_project(), operation="trace",
            qualified_name="route", use_model=True), cancellation_event=event)
    assert not heard and not history and not conversation.get_topic()
