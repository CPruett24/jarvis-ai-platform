"""Canonical C2 graph/traversal/impact and fail-closed freshness fixture tests."""
from dataclasses import FrozenInstanceError, replace
import threading

import pytest

from models.project_relationships import RelationshipKind, Resolution
from services import project_access as access
from services.project_analysis_index import analyze_project_relationships
from services.project_analysis_request import AnalysisBudgetExceeded, AnalysisLimits, AnalysisRequest
from services.project_graph import build_relationship_graph, traverse_relationships
from services.project_impact import potential_file_impact, potential_function_impact
from services.project_analysis_freshness import check_graph_publication, check_snapshot_freshness
from services.cancellation import OperationCancelled


CALLS, IMPORTS = RelationshipKind.CALLS, RelationshipKind.IMPORTS


@pytest.fixture
def project(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    access.register_project("fixture", tmp_path)
    access.select_project("fixture")
    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target
    yield write
    access._projects, access._active, access._revision = old


def analyze(limits=None, event=None, clock=lambda: 0):
    request = AnalysisRequest.capture(limits=limits, cancellation_event=event, clock=clock)
    return analyze_project_relationships(request), request


def symbol(result, name, path=None):
    matches = [s for s in result.symbols if s.qualified_name == name and (path is None or s.definition.path == path)]
    assert len(matches) == 1
    return matches[0].symbol_id


def names(result, path):
    symbols = {s.symbol_id: s for s in result.symbols}
    return tuple(symbols[node].qualified_name for node in path)


def chain(project):
    project("leaf.py", "def end():\n    pass\n")
    project("middle.py", "from leaf import end\ndef middle():\n    end()\n")
    project("root.py", "from middle import middle\ndef start():\n    middle()\n")


def test_cross_file_forward_and_reverse_paths_use_exact_canonical_edges(project):
    chain(project)
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    forward = traverse_relationships(graph, request, filename="root.py", qualified_name="start")
    reverse = traverse_relationships(graph, request, symbol_id=symbol(result, "end"), direction="reverse")
    assert [names(result, s.path) for s in forward.steps] == [("start",), ("start", "middle"), ("start", "middle", "end")]
    assert [names(result, s.path) for s in reverse.steps] == [("end",), ("end", "middle"), ("end", "middle", "start")]
    assert forward.complete and reverse.complete
    assert set(forward.steps[-1].relationship_path) == {a.relationship_id for a in graph.arcs}
    assert graph.analysis is result and graph.snapshot_id == result.snapshot.snapshot_id
    assert not graph.publication_ready and not forward.publication_ready
    assert dict(request.budget.usage.consumed)["visited_symbols"] == 6


def test_absolute_and_relative_import_dependencies_project_to_canonical_modules(project):
    project("pkg/__init__.py", "")
    project("pkg/leaf.py", "def end():\n    pass\n")
    project("pkg/middle.py", "from .leaf import end\n")
    project("root.py", "from pkg.middle import missing\nimport pkg.leaf\n")
    result, request = analyze()
    graph = build_relationship_graph(result, request, IMPORTS)
    edges = {r.relationship_id: r for r in result.relationships}
    projected = {(next(s.definition.path for s in result.symbols if s.symbol_id == a.origin_id),
                  next(s.definition.path for s in result.symbols if s.symbol_id == a.target_id)) for a in graph.arcs}
    assert projected == {("pkg/middle.py", "pkg/leaf.py"), ("root.py", "pkg/leaf.py")}
    assert all(edges[a.relationship_id].kind == IMPORTS for a in graph.arcs)
    reverse = traverse_relationships(graph, request, filename="pkg/leaf.py", direction="reverse")
    assert {s.node_id for s in reverse.steps} == {symbol(result, "<module>", p) for p in
                                                ("pkg/leaf.py", "pkg/middle.py", "root.py")}
    assert reverse.boundary_ids == graph.boundary_ids and not reverse.complete


@pytest.mark.parametrize("body,root,expected", [
    ("def a():\n    a()\n", "a", ("a", "a")),
    ("def a():\n    b()\ndef b():\n    a()\n", "a", ("a", "b", "a")),
])
def test_self_and_mutual_recursion_have_path_local_cycle_references(project, body, root, expected):
    project("main.py", body)
    result, request = analyze()
    trace = traverse_relationships(build_relationship_graph(result, request, CALLS), request,
                                   symbol_id=symbol(result, root))
    cycles = [s for s in trace.steps if s.classification == "cycle"]
    assert len(cycles) == 1 and names(result, cycles[0].path) == expected
    assert cycles[0].back_reference_path == (symbol(result, root),)
    assert trace.complete


def test_import_cycles_use_the_same_forward_records_in_reverse(project):
    project("a.py", "import b\n")
    project("b.py", "import a\n")
    result, request = analyze()
    graph = build_relationship_graph(result, request, IMPORTS)
    trace = traverse_relationships(graph, request, filename="a.py", direction="reverse")
    assert [s.classification for s in trace.steps] == ["root", "expanded", "cycle"]
    assert len(graph.arcs) == 2 and trace.complete


def test_diamond_shared_descendant_is_not_a_cycle(project):
    project("main.py", "def end():\n    pass\ndef left():\n    end()\ndef right():\n    end()\n"
            "def start():\n    left()\n    right()\n")
    result, request = analyze()
    trace = traverse_relationships(build_relationship_graph(result, request, CALLS), request,
                                   symbol_id=symbol(result, "start"))
    assert [names(result, s.path) for s in trace.steps] == [
        ("start",), ("start", "left"), ("start", "left", "end"),
        ("start", "right"), ("start", "right", "end")]
    shared = [s for s in trace.steps if s.classification == "shared"]
    assert len(shared) == 1 and names(result, shared[0].back_reference_path) == ("start", "left", "end")
    assert not any(s.classification == "cycle" for s in trace.steps)
    assert dict(request.budget.usage.consumed)["visited_symbols"] == 4


def test_shallower_revisit_expands_beyond_an_earlier_depth_cutoff(project):
    project("main.py", "def end():\n    pass\ndef shared():\n    end()\ndef b():\n    shared()\n"
            "def a():\n    b()\ndef z():\n    shared()\ndef start():\n    a()\n    z()\n")
    result, request = analyze()
    trace = traverse_relationships(build_relationship_graph(result, request, CALLS), request,
                                   symbol_id=symbol(result, "start"), max_depth=3)
    assert any(names(result, s.path) == ("start", "z", "shared", "end") for s in trace.steps)
    assert any(s.classification == "revisited" and names(result, s.path) == ("start", "z", "shared") for s in trace.steps)
    assert "depth" in trace.cutoff_reasons and not trace.complete


@pytest.mark.parametrize("limits,depth,reason", [
    ({}, 1, "depth"), ({"visited_symbols": 1}, None, "visited_symbols"),
    ({"traversed_edges": 1}, None, "traversed_edges"),
])
def test_depth_node_and_edge_limits_are_explicit_and_shared(project, limits, depth, reason):
    chain(project)
    result, request = analyze(replace(AnalysisLimits(), **limits))
    before = dict(request.budget.usage.consumed)
    trace = traverse_relationships(build_relationship_graph(result, request, CALLS), request,
                                   symbol_id=symbol(result, "start"), max_depth=depth)
    assert reason in trace.cutoff_reasons and not trace.complete
    after = dict(request.budget.usage.consumed)
    assert after["source_bytes"] == before["source_bytes"]
    assert after["relationships"] == before["relationships"]
    assert after["visited_symbols"] <= request.budget.limits.visited_symbols
    assert after["traversed_edges"] <= request.budget.limits.traversed_edges


def test_repeated_traversals_do_not_get_fresh_allowances(project):
    project("main.py", "def end():\n    pass\ndef start():\n    end()\n")
    result, request = analyze(replace(AnalysisLimits(), visited_symbols=2))
    graph = build_relationship_graph(result, request, CALLS)
    assert traverse_relationships(graph, request, symbol_id=symbol(result, "start")).complete
    again = traverse_relationships(graph, request, symbol_id=symbol(result, "start"))
    assert again.cutoff_reasons == ("visited_symbols",)
    assert dict(request.budget.usage.consumed)["visited_symbols"] == 2


def test_cancellation_during_traversal_is_a_safe_failure(project, monkeypatch):
    chain(project)
    event = threading.Event()
    result, request = analyze(event=event)
    graph = build_relationship_graph(result, request, CALLS)
    original = request.budget.consume
    def consume(**amounts):
        original(**amounts)
        if amounts.get("traversed_edges"):
            event.set()
    monkeypatch.setattr(request.budget, "consume", consume)
    with pytest.raises(OperationCancelled):
        traverse_relationships(graph, request, symbol_id=symbol(result, "start"))


def test_deadline_is_not_restarted_for_graph_or_traversal(project, monkeypatch):
    chain(project)
    tick = [0]
    result, request = analyze(clock=lambda: tick[0])
    graph = build_relationship_graph(result, request, CALLS)
    original = request.budget.consume
    def consume(**amounts):
        original(**amounts)
        if amounts.get("traversed_edges"):
            tick[0] = 5
    monkeypatch.setattr(request.budget, "consume", consume)
    trace = traverse_relationships(graph, request, symbol_id=symbol(result, "start"))
    assert "seconds" in trace.cutoff_reasons
    with pytest.raises(AnalysisBudgetExceeded):
        build_relationship_graph(result, request, CALLS)


@pytest.mark.parametrize("classification", [Resolution.INFERRED, Resolution.UNRESOLVED, Resolution.AMBIGUOUS, Resolution.INCOMPLETE])
def test_uncertain_edges_are_boundaries_not_confirmed_arcs(project, classification):
    project("main.py", "def end():\n    pass\ndef other():\n    pass\ndef start():\n    end()\n")
    result, request = analyze()
    original = result.relationships[0]
    candidates = tuple(s for s in result.symbols if s.qualified_name in {"end", "other"})
    uncertain = replace(original, resolution=classification, target=original.target if classification == Resolution.INFERRED else None,
                        candidates=candidates if classification == Resolution.AMBIGUOUS else ())
    result = replace(result, relationships=[uncertain])
    graph = build_relationship_graph(result, request, CALLS)
    trace = traverse_relationships(graph, request, symbol_id=symbol(result, "start"))
    assert not graph.arcs and trace.boundary_ids == (uncertain.relationship_id,)
    assert graph.analysis.relationships[0].resolution == classification and not trace.complete


def test_reverse_unknown_calls_prevent_project_wide_absence_claims(project):
    project("main.py", "def end():\n    pass\ndef dynamic(callback):\n    callback()\n")
    result, request = analyze()
    impact = potential_function_impact(result, request, qualified_name="end")
    assert not impact.affected and impact.traversal.boundary_ids and not impact.complete
    assert not check_graph_publication(impact, request).verified


def test_qualified_and_duplicate_targets_are_not_guessed(project):
    project("a/mod.py", "def Run():\n    pass\n")
    project("b/mod.py", "def Run():\n    pass\n")
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    assert traverse_relationships(graph, request, qualified_name="Run").status == "ambiguous"
    assert traverse_relationships(graph, request, filename="mod.py").status == "ambiguous"
    assert traverse_relationships(graph, request, filename="a/mod.py", qualified_name="Run").status == "resolved"
    assert traverse_relationships(graph, request, filename="a/mod.py", qualified_name="run").status == "not_found"
    assert traverse_relationships(graph, request, symbol_id=symbol(result, "Run", "b/mod.py")).status == "resolved"
    assert potential_file_impact(result, request, "mod.py", kind=IMPORTS).traversal.status == "ambiguous"


def test_call_and_import_impact_sets_remain_separate_and_inbound(project):
    chain(project)
    project("unused.py", "from leaf import end\n")
    result, request = analyze()
    function = potential_function_impact(result, request, qualified_name="end")
    assert {a.symbol_id for a in function.affected} == {symbol(result, "middle"), symbol(result, "start")}
    imports = potential_file_impact(result, request, "leaf.py", kind=IMPORTS)
    assert {a.symbol_id for a in imports.affected} == {symbol(result, "<module>", p) for p in ("middle.py", "root.py", "unused.py")}
    calls = potential_file_impact(result, request, "leaf.py", kind=CALLS)
    assert {a.symbol_id for a in calls.affected} == {symbol(result, "middle"), symbol(result, "start")}
    outbound = potential_function_impact(result, request, qualified_name="start")
    assert not outbound.affected
    assert function.kind == calls.kind == CALLS and imports.kind == IMPORTS
    assert all(a.relationship_path for a in function.affected + imports.affected)
    assert "Potentially affected" in function.interpretation


def test_canonical_order_and_contracts_reject_invented_arcs(project):
    chain(project)
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    reordered = replace(result, symbols=tuple(reversed(result.symbols)), relationships=tuple(reversed(result.relationships)))
    other = build_relationship_graph(reordered, request, CALLS)
    assert graph.node_ids == other.node_ids and graph.arcs == other.arcs
    with pytest.raises(ValueError):
        replace(graph, arcs=())
    with pytest.raises(ValueError):
        replace(graph, arcs=[replace(graph.arcs[0], target_id="invented")])
    with pytest.raises(FrozenInstanceError):
        graph.kind = IMPORTS


def test_freshness_rechecks_inventory_and_digests_using_same_budget(project):
    chain(project)
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    before = dict(request.budget.usage.consumed)["source_bytes"]
    check = check_graph_publication(graph, request)
    assert check.verified and check.snapshot_id == graph.snapshot_id
    assert dict(request.budget.usage.consumed)["source_bytes"] == before * 2
    assert not graph.publication_ready  # Successful checks are not permanent freshness stamps.


@pytest.mark.parametrize("change", ["added_caller", "binding", "deleted_file"])
def test_stale_inventory_binding_or_deleted_source_fails_closed(project, change):
    chain(project)
    result, request = analyze()
    if change == "added_caller":
        project("new.py", "from leaf import end\ndef another():\n    end()\n")
    elif change == "binding":
        project("root.py", "from leaf import end as middle\ndef start():\n    middle()\n")
    else:
        # This disposable file was created by this test, never repository data.
        (request.context.root / "middle.py").unlink()
    check = check_snapshot_freshness(result, request)
    assert check.state == "stale" and not check.verified


@pytest.mark.parametrize("partial", ["discovery", "parse"])
def test_incomplete_analysis_can_never_pass_publication_gate(project, monkeypatch, partial):
    chain(project)
    if partial == "parse":
        project("broken.py", "def broken(:\n")
    else:
        from services import project_retrieval
        from models.source_evidence import RetrievalStatus
        original = project_retrieval.discover
        def discover(*args, **kwargs):
            listing = original(*args, **kwargs)
            listing.status = RetrievalStatus.PARTIAL
            listing.limits_reached.append("entries")
            return listing
        monkeypatch.setattr(project_retrieval, "discover", discover)
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    trace = traverse_relationships(graph, request, qualified_name="end", direction="reverse")
    assert not trace.complete and graph.analysis.snapshot.coverage is result.snapshot.coverage
    assert check_snapshot_freshness(result, request).state == "unverified"
    assert not check_graph_publication(trace, request).verified


def test_authorization_revision_and_two_roots_are_never_cross_linked(project, tmp_path):
    chain(project)
    result, request = analyze()
    access.register_project("fixture", request.context.root)
    assert check_snapshot_freshness(result, request).state == "stale"
    with pytest.raises(access.ProjectAccessError):
        build_relationship_graph(result, request, CALLS)
    second = tmp_path / "second"
    second.mkdir()
    (second / "main.py").write_text("def end():\n    pass\n")
    access.register_project("second", second)
    access.select_project("second")
    other, other_request = analyze()
    with pytest.raises(access.ProjectAccessError):
        build_relationship_graph(result, other_request, CALLS)
    assert set(build_relationship_graph(other, other_request, CALLS).node_ids).isdisjoint(s.symbol_id for s in result.symbols)


def test_freshness_budget_exhaustion_and_cancellation_are_unverified(project):
    source = "def end():\n    pass\n"
    project("main.py", source)
    result, request = analyze(replace(AnalysisLimits(), source_bytes=len(source.encode()) + 1))
    assert check_snapshot_freshness(result, request).state == "unverified"
    event = threading.Event()
    result, request = analyze(event=event)
    event.set()
    assert check_snapshot_freshness(result, request).state == "cancelled"


def test_new_caller_invalidates_a_previously_empty_reverse_result(project):
    project("leaf.py", "def end():\n    pass\n")
    result, request = analyze()
    impact = potential_function_impact(result, request, qualified_name="end")
    assert impact.complete and not impact.affected
    project("late.py", "from leaf import end\ndef caller():\n    end()\n")
    assert check_graph_publication(impact, request).state == "stale"


def test_second_inventory_detects_addition_during_fingerprint_validation(project, monkeypatch):
    chain(project)
    result, request = analyze()
    from services import project_analysis_freshness
    original = project_analysis_freshness.read_analysis_source
    def read(*args, **kwargs):
        fresh = original(*args, **kwargs)
        project("late.py", "pass\n")
        return fresh
    monkeypatch.setattr(project_analysis_freshness, "read_analysis_source", read)
    assert check_snapshot_freshness(result, request).state == "stale"


def test_equal_size_binding_edit_still_invalidates_digest(project):
    chain(project)
    result, request = analyze()
    path = request.context.root / "root.py"
    before = path.stat().st_size
    project("root.py", "from middle import Middle\ndef start():\n    Middle()\n")
    assert path.stat().st_size == before
    check = check_snapshot_freshness(result, request)
    assert check.state == "stale" and check.reasons == ("source_digest_changed:root.py",)


@pytest.mark.parametrize("action", ["revoke", "selection"])
def test_authorization_changes_during_traversal_fail_before_return(project, tmp_path, monkeypatch, action):
    chain(project)
    other = tmp_path / "other"
    other.mkdir()
    access.register_project("other", other)
    result, request = analyze()
    graph = build_relationship_graph(result, request, CALLS)
    original = request.budget.consume
    def consume(**amounts):
        original(**amounts)
        if amounts.get("traversed_edges"):
            if action == "revoke":
                access.revoke_project("fixture")
            else:
                access.select_project("other")
    monkeypatch.setattr(request.budget, "consume", consume)
    with pytest.raises(access.ProjectAccessError):
        traverse_relationships(graph, request, qualified_name="start")


def test_fingerprint_read_denial_cannot_become_verified(project, monkeypatch):
    chain(project)
    result, request = analyze()
    from services import project_analysis_freshness
    from models.source_evidence import RetrievalResult, RetrievalStatus
    def denied(request, path):
        return RetrievalResult(request.context.project_id, request.context.revision, "read",
                               RetrievalStatus.DENIED, error="fixture denial")
    monkeypatch.setattr(project_analysis_freshness, "read_analysis_source", denied)
    check = check_snapshot_freshness(result, request)
    assert check.state == "unverified" and not check.verified


def test_contract_rejects_reversed_or_fabricated_trace_paths(project):
    chain(project)
    result, request = analyze()
    trace = traverse_relationships(build_relationship_graph(result, request, CALLS), request, qualified_name="start")
    last = trace.steps[-1]
    with pytest.raises(ValueError):
        replace(trace, steps=[replace(last, relationship_path=tuple(reversed(last.relationship_path)))])
    with pytest.raises(ValueError):
        replace(trace, steps=[replace(last, classification="cycle")])
    with pytest.raises(ValueError):
        traverse_relationships(trace.graph, request, qualified_name="start", max_depth=5)


def test_impact_node_cutoff_retains_only_confirmed_visited_connections(project):
    chain(project)
    result, request = analyze(replace(AnalysisLimits(), visited_symbols=2))
    impact = potential_function_impact(result, request, qualified_name="end")
    assert {a.symbol_id for a in impact.affected} == {symbol(result, "middle")}
    assert impact.traversal.cutoff_reasons == ("visited_symbols",)
    assert not impact.complete
