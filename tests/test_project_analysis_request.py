from dataclasses import FrozenInstanceError, replace
import threading

import pytest

from models.project_relationships import AnalysisCoverage, AnalysisResult, AnalysisSnapshot
from services import project_access as access
from services.cancellation import OperationCancelled
from services.project_analysis_request import AnalysisBudget, AnalysisBudgetExceeded, AnalysisLimits, AnalysisRequest


@pytest.fixture
def project(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    access.register_project("first", first)
    access.register_project("second", second)
    access.select_project("first")
    yield first, second
    access._projects, access._active, access._revision = old


def test_approved_limits_are_explicit():
    limits = AnalysisLimits()
    assert (limits.python_files, limits.source_bytes, limits.file_bytes) == (256, 8 * 1024 * 1024, 512 * 1024)
    assert (limits.ast_nodes_per_file, limits.ast_nodes, limits.relationships) == (50000, 200000, 10000)
    assert (limits.depth, limits.visited_symbols, limits.traversed_edges) == (4, 200, 500)
    assert (limits.seconds, limits.evidence_excerpts, limits.evidence_files) == (5.0, 8, 6)
    assert (limits.payload_bytes, limits.selected_relationships) == (24 * 1024, 32)


@pytest.mark.parametrize("resource", ["python_files", "source_bytes", "ast_nodes", "relationships",
    "visited_symbols", "traversed_edges", "evidence_excerpts", "evidence_files", "payload_bytes", "selected_relationships"])
def test_all_additive_budgets_exhaust_without_partial_charges(resource):
    budget = AnalysisBudget(replace(AnalysisLimits(), **{resource: 1}), clock=lambda: 0)
    budget.consume(**{resource: 1})
    with pytest.raises(AnalysisBudgetExceeded) as failure:
        budget.consume(**{resource: 1})
    assert failure.value.resource == resource
    assert dict(budget.usage.consumed)[resource] == 1
    assert budget.usage.exhausted == (resource,)


def test_nested_operations_share_one_budget_and_atomic_charges():
    budget = AnalysisBudget(replace(AnalysisLimits(), python_files=2, source_bytes=10), clock=lambda: 0)
    def read_stage(shared):
        shared.consume(source_bytes=5)
    def parse_stage(shared):
        read_stage(shared)
        shared.consume(python_files=1, ast_nodes=3)
    parse_stage(budget)
    parse_stage(budget)
    with pytest.raises(AnalysisBudgetExceeded):
        budget.consume(ast_nodes=5, python_files=1)
    assert dict(budget.usage.consumed)["ast_nodes"] == 6
    assert dict(budget.usage.consumed)["source_bytes"] == 10
    with pytest.raises(FrozenInstanceError):
        budget.limits.python_files = 10


def test_per_file_and_depth_ceilings_are_distinct_from_aggregate_work():
    budget = AnalysisBudget(clock=lambda: 0)
    budget.check_file(512 * 1024, 50000)
    budget.check_depth(4)
    assert dict(budget.usage.consumed)["source_bytes"] == 0
    for action, resource in [(lambda: budget.check_file(512 * 1024 + 1), "file_bytes"),
                             (lambda: budget.check_file(1, 50001), "ast_nodes_per_file"),
                             (lambda: budget.check_depth(5), "depth")]:
        with pytest.raises(AnalysisBudgetExceeded) as failure:
            action()
        assert failure.value.resource == resource


def test_deadline_does_not_reset_between_stages():
    tick = [10.0]
    budget = AnalysisBudget(clock=lambda: tick[0])
    tick[0] = 14.9
    budget.consume(python_files=1)
    tick[0] = 15.0
    with pytest.raises(AnalysisBudgetExceeded) as failure:
        budget.consume(ast_nodes=1)
    assert failure.value.resource == "seconds"
    assert dict(budget.usage.consumed)["ast_nodes"] == 0


def test_cancellation_is_distinct_and_preserves_usage():
    event = threading.Event()
    budget = AnalysisBudget(cancellation_event=event, clock=lambda: 0)
    budget.consume(python_files=1)
    event.set()
    for action in [budget.check, lambda: budget.consume(ast_nodes=1), lambda: budget.check_depth(1)]:
        with pytest.raises(OperationCancelled):
            action()
    assert dict(budget.usage.consumed)["python_files"] == 1
    assert not budget.usage.exhausted


def test_shared_budget_handles_concurrent_consumers_without_overspending():
    budget = AnalysisBudget(replace(AnalysisLimits(), python_files=3), clock=lambda: 0)
    accepted = []
    def consume():
        try:
            budget.consume(python_files=1)
            accepted.append(True)
        except AnalysisBudgetExceeded:
            pass
    workers = [threading.Thread(target=consume) for _ in range(10)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(2)
        assert not worker.is_alive()
    assert len(accepted) == dict(budget.usage.consumed)["python_files"] == 3


def test_usage_is_an_immutable_snapshot():
    budget = AnalysisBudget(clock=lambda: 0)
    before = budget.usage
    budget.consume(python_files=1)
    assert dict(before.consumed)["python_files"] == 0
    with pytest.raises(FrozenInstanceError):
        before.exhausted = ("changed",)


@pytest.mark.parametrize("changes", [{"seconds": float("nan")}, {"seconds": float("inf")},
    {"seconds": True}, {"python_files": False}, {"ast_nodes": -1}, {"file_bytes": 512 * 1024 + 1}])
def test_invalid_limits_are_rejected(changes):
    with pytest.raises(ValueError):
        AnalysisLimits(**changes)


@pytest.mark.parametrize("amounts", [{"python_files": -1}, {"python_files": True},
    {"python_files": 1.5}, {"unknown": 1}, {"seconds": 1}, {"depth": 1}])
def test_budget_cannot_be_refunded_or_charged_unknown_units(amounts):
    budget = AnalysisBudget(clock=lambda: 0)
    with pytest.raises(ValueError):
        budget.consume(**amounts)


def test_captured_context_is_explicit_and_never_authorizes_from_cwd(project, monkeypatch):
    first, second = project
    request = AnalysisRequest.capture(clock=lambda: 0)
    assert request.context.root == first
    assert request.identity.project_id == "first"
    before = access.list_projects()
    monkeypatch.chdir(second)
    assert AnalysisRequest.capture(clock=lambda: 0).identity == request.identity
    with pytest.raises(access.ProjectAccessError):
        AnalysisRequest.capture(str(second), clock=lambda: 0)
    assert access.list_projects() == before
    # Checkpoint 1 does not remove the legacy analyzer restriction.
    with pytest.raises(access.ProjectAccessError):
        access.require_legacy_project()


@pytest.mark.parametrize("change", ["selection", "revision", "revocation"])
def test_authorization_is_rechecked_before_publication(project, change):
    first, _ = project
    request = AnalysisRequest.capture(clock=lambda: 0)
    result = AnalysisResult(AnalysisSnapshot(request.identity, AnalysisCoverage(discovery_complete=True)))
    assert request.validate_for_publication(result) is result
    if change == "selection":
        access.select_project("second")
    elif change == "revision":
        access.register_project("first", first)
    else:
        access.revoke_project("first")
    with pytest.raises(access.ProjectAccessError):
        request.validate_for_publication(result)


def test_publication_rejects_another_authorized_project_and_cancellation(project):
    first, _ = project
    event = threading.Event()
    request = AnalysisRequest.capture(cancellation_event=event, clock=lambda: 0)
    access.select_project("second")
    other = AnalysisRequest.capture(clock=lambda: 0)
    result = AnalysisResult(AnalysisSnapshot(other.identity, AnalysisCoverage(discovery_complete=True)))
    access.select_project("first")
    with pytest.raises(access.ProjectAccessError):
        request.validate_for_publication(result)
    event.set()
    with pytest.raises(OperationCancelled):
        request.check_authorization()
