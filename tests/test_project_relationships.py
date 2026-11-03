from dataclasses import FrozenInstanceError, replace
import hashlib
import os

import pytest

from models.project_relationships import (
    AnalysisCoverage, AnalysisResult, AnalysisSnapshot, FileDiagnostic, ProjectIdentity,
    RelationshipAnswerEvidence, RelationshipKind, RelationshipRecord, Resolution,
    SourceFingerprint, SourceLocation, SymbolKind, SymbolRecord, TraceResult,
)
from models.source_evidence import SourceExcerpt


DIGEST = hashlib.sha256(b"source").hexdigest()


@pytest.fixture
def project(tmp_path):
    return ProjectIdentity("fixture", os.path.normcase(str(tmp_path.resolve())), 1)


def location(project, path="a.py", start=1, end=4, source_id="S1"):
    return SourceLocation(project, path, source_id, DIGEST, start, end)


def symbol(project, name="run", path="a.py"):
    return SymbolRecord(name, SymbolKind.FUNCTION, location(project, path))


def relationship(project, resolution=Resolution.CONFIRMED_STATIC):
    origin, target = symbol(project), symbol(project, "save", "b.py")
    return RelationshipRecord(RelationshipKind.CALLS, origin,
                              target if resolution in {Resolution.CONFIRMED_STATIC, Resolution.INFERRED} else None,
                              "save()", location(project, start=2, end=2), resolution, "static binding")


def analysis(project, record=None):
    record = record or relationship(project)
    coverage = AnalysisCoverage(["a.py", "b.py"], ["a.py", "b.py"], discovery_complete=True)
    snapshot = AnalysisSnapshot(project, coverage, [SourceFingerprint(p, DIGEST) for p in coverage.parsed])
    return AnalysisResult(snapshot, [record.origin, record.target] if record.target else [record.origin], [record])


def excerpt(project, path="a.py", source_id="S1"):
    return SourceExcerpt(source_id, project.project_id, project.authorization_revision, path, 1, 4,
                         "one\ntwo\nthree\nfour", "now", (1, 10), DIGEST)


def test_symbol_identity_is_stable_but_scope_and_location_are_distinct(project):
    first = symbol(project)
    assert first.symbol_id == symbol(project).symbol_id
    changed_digest = replace(first.definition, digest="f" * 64, source_id="Snew")
    assert replace(first, definition=changed_digest).symbol_id == first.symbol_id
    variants = [symbol(project, "Class.run"), symbol(project, "outer.<locals>.run"),
                symbol(project, path="b.py"), replace(first, kind=SymbolKind.METHOD),
                replace(first, definition=replace(first.definition, start_line=2)),
                symbol(replace(project, authorization_revision=2)),
                symbol(replace(project, project_id="other")),
                symbol(replace(project, root_identity=project.root_identity + "-other"))]
    assert len({s.symbol_id for s in variants} | {first.symbol_id}) == len(variants) + 1


@pytest.mark.parametrize("path", ["../a.py", "a/../b.py", "/a.py", "C:/a.py", "a\\b.py", "a.py:stream", "a//b.py", "./a.py"])
def test_relative_provenance_paths_cannot_escape(project, path):
    with pytest.raises(ValueError):
        location(project, path)


@pytest.mark.parametrize("changes", [
    {"start_line": 0}, {"start_line": True}, {"end_line": 0}, {"start_line": 5},
    {"start_column": -1}, {"end_line": 1, "start_column": 2, "end_column": 1},
    {"digest": "hash"}, {"source_id": ""},
])
def test_source_range_and_identity_invariants(project, changes):
    with pytest.raises(ValueError):
        replace(location(project), **changes)


@pytest.mark.parametrize("resolution", list(Resolution))
def test_relationship_classification_is_explicit(project, resolution):
    if resolution == Resolution.AMBIGUOUS:
        with pytest.raises(ValueError):
            relationship(project, resolution)
    else:
        record = relationship(project, resolution)
        assert record.resolution == resolution


def test_unresolved_and_ambiguous_never_claim_a_unique_target(project):
    first, second = symbol(project, "save", "b.py"), symbol(project, "save", "c.py")
    base = relationship(project, Resolution.UNRESOLVED)
    assert base.target is None
    ambiguous = replace(base, resolution=Resolution.AMBIGUOUS, candidates=[first, second])
    assert ambiguous.target is None and len(ambiguous.candidates) == 2
    assert ambiguous.relationship_id == replace(ambiguous, candidates=[second, first]).relationship_id
    with pytest.raises(ValueError):
        replace(base, target=first)
    with pytest.raises(ValueError):
        replace(ambiguous, candidates=[first, first])
    with pytest.raises(ValueError):
        replace(base, resolution=Resolution.CONFIRMED_STATIC)


def test_relationship_provenance_and_project_boundaries(project):
    record = relationship(project)
    for changes in [{"location": location(project, "b.py")},
                    {"location": location(project, start=5, end=5)},
                    {"location": replace(record.location, digest="f" * 64)},
                    {"target": symbol(replace(project, authorization_revision=2))},
                    {"supporting_sources": [location(replace(project, project_id="other"))]}]:
        with pytest.raises(ValueError):
            replace(record, **changes)
    assert record.relationship_id == relationship(project).relationship_id
    assert record.relationship_id != replace(record, expression="alias()").relationship_id


def test_relationship_and_result_collections_are_defensive(project):
    first, second = symbol(project, "save", "b.py"), symbol(project, "save", "c.py")
    candidates = [first, second]
    sources = [location(project)]
    record = replace(relationship(project, Resolution.UNRESOLVED), resolution=Resolution.AMBIGUOUS,
                     candidates=candidates, supporting_sources=sources)
    candidates.clear()
    sources.clear()
    assert len(record.candidates) == 2 and len(record.supporting_sources) == 1
    result = analysis(project)
    symbols, edges = list(result.symbols), list(result.relationships)
    copied = replace(result, symbols=symbols, relationships=edges)
    symbols.clear()
    edges.clear()
    assert len(copied.symbols) == 2 and len(copied.relationships) == 1
    with pytest.raises(FrozenInstanceError):
        record.reason = "changed"


def test_root_identity_and_typed_classifications_are_required(project):
    with pytest.raises(ValueError):
        replace(project, root_identity="relative")
    with pytest.raises(ValueError):
        replace(symbol(project), kind="function")
    with pytest.raises(ValueError):
        replace(relationship(project), resolution="confirmed_static")
    with pytest.raises(ValueError):
        AnalysisCoverage(discovered="a.py")


def test_records_defensively_copy_caller_collections(project):
    paths, parsed = ["a.py"], ["a.py"]
    coverage = AnalysisCoverage(paths, parsed, discovery_complete=True)
    fingerprints = [SourceFingerprint("a.py", DIGEST)]
    options = [["language", "python"]]
    snapshot = AnalysisSnapshot(project, coverage, fingerprints, options)
    paths.append("b.py")
    parsed.clear()
    fingerprints.clear()
    options[0][1] = "javascript"
    assert snapshot.coverage.discovered == snapshot.coverage.parsed == ("a.py",)
    assert snapshot.options == (("language", "python"),)
    assert len(snapshot.fingerprints) == 1
    with pytest.raises(FrozenInstanceError):
        snapshot.schema_version = "changed"


def test_partial_coverage_cannot_claim_completeness(project):
    complete = AnalysisCoverage(["a.py"], ["a.py"], discovery_complete=True)
    assert complete.complete
    for changes in [{"discovery_complete": False}, {"cancelled": True},
                    {"budget_exhausted": ["seconds"]}, {"parsed": []}]:
        assert not replace(complete, **changes).complete
    for category in ("skipped", "parse_failures", "unsupported"):
        assert not replace(complete, parsed=[], **{category: [FileDiagnostic("a.py", "reason")]}).complete
    excluded = replace(complete, parsed=[], excluded=[FileDiagnostic("a.py", "policy exclusion")])
    assert excluded.complete  # Complete only within the declared permitted scope.
    with pytest.raises(ValueError):
        replace(complete, skipped=[FileDiagnostic("a.py", "double counted")])
    with pytest.raises(ValueError):
        replace(complete, parsed=["unknown.py"])
    with pytest.raises(ValueError):
        AnalysisCoverage(["a.js"], ["a.js"], discovery_complete=True)


def test_snapshot_identity_covers_scope_inventory_fingerprints_and_coverage(project):
    snapshot = analysis(project).snapshot
    assert snapshot.snapshot_id == replace(snapshot, fingerprints=list(reversed(snapshot.fingerprints)),
        coverage=replace(snapshot.coverage, discovered=["b.py", "a.py"], parsed=["b.py", "a.py"])).snapshot_id
    variants = [replace(snapshot, project=replace(project, authorization_revision=2)),
                replace(snapshot, project=replace(project, root_identity=project.root_identity + "-other")),
                replace(snapshot, schema_version="c2.2"), replace(snapshot, options=[("include_tests", "true")]),
                replace(snapshot, fingerprints=[SourceFingerprint("a.py", "f" * 64), snapshot.fingerprints[1]]),
                replace(snapshot, coverage=replace(snapshot.coverage, discovery_complete=False)),
                replace(snapshot, coverage=replace(snapshot.coverage, discovered=["a.py", "b.py", "c.py"]))]
    assert all(v.snapshot_id != snapshot.snapshot_id for v in variants)
    with pytest.raises(ValueError):
        replace(snapshot, fingerprints=[])


def test_analysis_cannot_contain_unknown_or_stale_records(project):
    result = analysis(project)
    for changes in [{"symbols": result.symbols[:1]}, {"symbols": result.symbols * 2},
                    {"snapshot": replace(result.snapshot, project=replace(project, authorization_revision=2))},
                    {"snapshot": replace(result.snapshot, fingerprints=[SourceFingerprint("a.py", "f" * 64),
                                                                       result.snapshot.fingerprints[1]])}]:
        with pytest.raises(ValueError):
            replace(result, **changes)


def test_trace_contract_preserves_cycles_frontier_and_incompleteness(project):
    result = analysis(project)
    edge = result.relationships[0].relationship_id
    trace = TraceResult(result, result.symbols[0].symbol_id, "forward", [edge], [edge])
    assert trace.complete and trace.cycle_relationship_ids == (edge,)
    assert not replace(trace, cutoff_reasons=["depth"]).complete
    assert not replace(trace, frontier_symbol_ids=[result.symbols[1].symbol_id]).complete
    for changes in [{"root_symbol_id": "unknown"}, {"relationship_ids": ["unknown"]},
                    {"cycle_relationship_ids": ["unknown"]}]:
        with pytest.raises(ValueError):
            replace(trace, **changes)


def test_answer_evidence_requires_actual_covering_snapshot_sources(project):
    result = analysis(project)
    selected = [result.relationships[0].relationship_id]
    sources = [excerpt(project), excerpt(project, "b.py")]
    # C1 source IDs must be unique per file/range in an answer packet.
    sources[1] = replace(sources[1], source_id="S2")
    target = replace(result.symbols[1], definition=replace(result.symbols[1].definition, source_id="S2"))
    edge = replace(result.relationships[0], target=target)
    result = replace(result, symbols=[result.symbols[0], target], relationships=[edge])
    selected = [edge.relationship_id]
    packet = RelationshipAnswerEvidence(result, selected, sources)
    selected.clear()
    sources.clear()
    assert len(packet.relationship_ids) == 1 and len(packet.excerpts) == 2
    for changes in [{"relationship_ids": ["unknown"]}, {"excerpts": packet.excerpts[:1]},
                    {"excerpts": [replace(packet.excerpts[0], digest="f" * 64), packet.excerpts[1]]},
                    {"excerpts": [replace(packet.excerpts[0], revision=2), packet.excerpts[1]]},
                    {"excerpts": [replace(packet.excerpts[0], start_line=3, text="three\nfour"), packet.excerpts[1]]},
                    {"excerpts": [replace(packet.excerpts[0], signature=[1, 10]), packet.excerpts[1]]}]:
        with pytest.raises(ValueError):
            replace(packet, **changes)
    with pytest.raises(ValueError):
        SourceLocation.from_excerpt(replace(project, authorization_revision=2), packet.excerpts[0])
