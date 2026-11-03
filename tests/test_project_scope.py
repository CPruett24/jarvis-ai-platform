"""C3 contract-only fixtures: no analyzer, source imports, model, or publication."""
from dataclasses import FrozenInstanceError, replace
import threading

import pytest

from models.project_relationships import (
    AnalysisCoverage, AnalysisSnapshot, FileDiagnostic, ProjectIdentity, RelationshipKind,
    RelationshipRecord, Resolution, SourceLocation, SymbolKind, SymbolRecord,
)
from models.project_scope import (
    AnalysisScope, SupportClosure, ScopedCoverage, ScopedRelationshipResult,
    ScopeKind, LanguagePolicy, QuerySemantics, CoverageStatus, CompletenessClaim,
    EvidenceSelection, PublicationEligibility, C3_SCOPE_SCHEMA,
)
from services import project_access as access
from services.project_analysis_request import AnalysisRequest, AnalysisLimits
from services.project_analysis_freshness import check_graph_publication
from services.cancellation import OperationCancelled


@pytest.fixture
def declared(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    root = tmp_path / "authorized"
    root.mkdir()
    access.register_project("c3", root)
    access.select_project("c3")
    request = AnalysisRequest.capture(clock=lambda: 0)
    identity = request.identity
    def location(path, start=1, end=4, digest="a" * 64):
        return SourceLocation(identity, path, "S" + path, digest, start, end)
    support_source = location("voice/output.py")
    target = SymbolRecord("speak", SymbolKind.FUNCTION, support_source)
    support = SupportClosure(identity, (support_source.path,), (support_source,), closed=True, depth=1)
    scope = AnalysisScope(identity, ScopeKind.FILES, ("commands/run.py",), ("commands/run.py",),
        support, target, RelationshipKind.CALLS, "reverse", QuerySemantics.DIRECT)
    caller = SymbolRecord("run", SymbolKind.FUNCTION, location("commands/run.py"))
    edge = RelationshipRecord(RelationshipKind.CALLS, caller, target, "speak", location("commands/run.py", 2, 2),
                              Resolution.CONFIRMED_STATIC, "lexical_or_imported_binding")
    yield request, scope, edge
    access._projects, access._active, access._revision = old


def complete(scope, **changes):
    return ScopedCoverage(scope, CoverageStatus.COMPLETE, scope.search_files, scope.search_files,
                          inventory_complete=True, **changes)


def test_valid_explicit_file_scope_and_disabled_complete_metadata(declared):
    request, scope, edge = declared
    assert request.validate_scope(scope) is scope
    result = ScopedRelationshipResult(complete(scope), Resolution.CONFIRMED_STATIC,
        CompletenessClaim.SCOPED_COMPLETE, EvidenceSelection.COMPLETE, (edge,))
    assert result.exhaustive and not result.publication_ready
    assert result.publication is PublicationEligibility.DISABLED
    with pytest.raises(ValueError):
        check_graph_publication(result, request)
    with pytest.raises(access.ProjectAccessError):
        request.validate_for_publication(result)


def test_valid_directory_scope_records_non_python_without_incompleteness(declared):
    request, scope, _ = declared
    scope = replace(scope, kind=ScopeKind.DIRECTORY, roots=("commands",))
    coverage = complete(scope, non_python_files=("commands/README.md",))
    assert request.validate_scope(scope) is scope
    assert coverage.status == CoverageStatus.COMPLETE
    assert scope.support.required_files == ("voice/output.py",)


def test_project_wide_and_narrower_claims_are_distinct(declared):
    request, scope, edge = declared
    project = replace(scope, kind=ScopeKind.PROJECT_PYTHON, roots=(),
        search_files=("commands/run.py", "voice/output.py"), support=SupportClosure(scope.project, closed=True))
    assert request.validate_scope(project) is project
    result = ScopedRelationshipResult(complete(project), Resolution.CONFIRMED_STATIC,
        CompletenessClaim.PROJECT_COMPLETE, EvidenceSelection.COMPLETE, (edge,))
    assert result.exhaustive and not result.publication_ready
    with pytest.raises(ValueError):
        replace(result, coverage=complete(scope))
    narrowed = replace(project, excluded_paths=("tests",))
    with pytest.raises(ValueError):
        replace(result, coverage=complete(narrowed))


def test_order_independent_identity_and_defensive_immutability(declared):
    _, scope, _ = declared
    paths = ["commands/z.py", "commands/run.py"]
    first = replace(scope, roots=paths, search_files=paths)
    second = replace(scope, roots=list(reversed(paths)), search_files=list(reversed(paths)))
    paths.append("commands/injected.py")
    assert first == second and first.scope_id == second.scope_id
    assert first.scope_id.startswith("C3S") and first.schema_version == C3_SCOPE_SCHEMA
    assert "commands/injected.py" not in first.search_files
    with pytest.raises(FrozenInstanceError):
        first.direction = "forward"


@pytest.mark.parametrize("change", ["files", "direction", "semantics", "target", "project", "support", "exclusions"])
def test_scope_changes_invalidate_identity(declared, change):
    _, scope, _ = declared
    if change == "files":
        other = replace(scope, roots=("other.py",), search_files=("other.py",))
    elif change == "direction":
        other = replace(scope, direction="forward")
    elif change == "semantics":
        other = replace(scope, semantics=QuerySemantics.TRANSITIVE)
    elif change == "target":
        other = replace(scope, target=replace(scope.target, qualified_name="Speak"))
    elif change == "project":
        project = replace(scope.project, authorization_revision=scope.project.authorization_revision + 1)
        source = replace(scope.support.sources[0], project=project)
        other = replace(scope, project=project, support=SupportClosure(project, (source.path,), (source,), True),
                        target=replace(scope.target, definition=source))
    elif change == "support":
        other = replace(scope, support=replace(scope.support, required_files=scope.support.required_files + ("voice/helper.py",), closed=False))
    else:
        scope = replace(scope, kind=ScopeKind.DIRECTORY, roots=("commands",))
        other = replace(scope, excluded_paths=("commands/tests",))
    assert other.scope_id != scope.scope_id


def test_content_and_acquisition_state_do_not_renew_scope_identity(declared):
    _, scope, _ = declared
    source = replace(scope.support.sources[0], digest="b" * 64)
    changed = replace(scope, support=replace(scope.support, sources=(source,)),
                      target=replace(scope.target, definition=source))
    missing = replace(scope, support=replace(scope.support, sources=(), closed=False))
    assert changed.scope_id == missing.scope_id == scope.scope_id


@pytest.mark.parametrize("path", ["../a.py", "commands/../a.py", "/a.py", "C:/a.py", "a\\b.py",
    "a.py:stream", "a//b.py", "./a.py", "commands/*.py", "commands/a?.py", " a.py", "a.py\x00"])
def test_path_traversal_patterns_and_noncanonical_paths_rejected(declared, path):
    _, scope, _ = declared
    with pytest.raises(ValueError):
        replace(scope, roots=(path,), search_files=(path,))
    with pytest.raises(ValueError):
        replace(scope.support, required_files=(path,), sources=(), closed=False)


@pytest.mark.parametrize("changes", [
    {"kind": "files"}, {"kind": ScopeKind.DIRECTORY, "roots": ()},
    {"language": "python_only"}, {"language": "javascript"}, {"schema_version": "c2.2"},
    {"analysis_policy": "unrecognized"}, {"direction": "both"}, {"semantics": "direct"},
    {"roots": ("commands/run.py", "commands/run.py")},
    {"search_files": ("commands/run.py", "commands/RUN.py")},
    {"search_files": ("commands/run.py", "hidden.py")},
    {"excluded_paths": ("commands/run.py",)}, {"excluded_paths": ("unrelated",)},
    {"kind": ScopeKind.DIRECTORY, "roots": ("commands", "commands/nested")},
])
def test_unsupported_or_contradictory_scope_declarations(declared, changes):
    _, scope, _ = declared
    with pytest.raises(ValueError):
        replace(scope, **changes)


def test_search_support_roles_and_case_aliases_cannot_overlap(declared):
    _, scope, _ = declared
    for path in ("commands/run.py", "commands/RUN.py"):
        source = replace(scope.support.sources[0], path=path)
        with pytest.raises(ValueError):
            replace(scope, support=SupportClosure(scope.project, (path,), (source,), True))


@pytest.mark.parametrize("change", ["revision", "root", "project"])
def test_unauthorized_identity_cannot_be_admitted_or_register_itself(declared, change):
    request, scope, _ = declared
    before = access._projects.copy(), access._active, access._revision
    project = replace(scope.project, **({"authorization_revision": 999} if change == "revision" else
        {"root_identity": scope.project.root_identity + "-unauthorized"} if change == "root" else {"project_id": "unauthorized"}))
    source = replace(scope.support.sources[0], project=project)
    forged = replace(scope, project=project, support=SupportClosure(project, (source.path,), (source,), True),
                     target=replace(scope.target, definition=source))
    with pytest.raises(access.ProjectAccessError):
        request.validate_scope(forged)
    assert (access._projects, access._active, access._revision) == before


def test_cross_project_and_cross_revision_support_are_rejected(declared):
    _, scope, _ = declared
    for project in (replace(scope.project, project_id="other"), replace(scope.project, authorization_revision=999)):
        foreign = replace(scope.support.sources[0], project=project)
        with pytest.raises(ValueError):
            replace(scope.support, sources=(foreign,))
        with pytest.raises(ValueError):
            replace(scope, target=replace(scope.target, definition=foreign))


@pytest.mark.parametrize("changes", [
    {"required_files": tuple(f"support{i}.py" for i in range(7)), "sources": (), "closed": False},
    {"depth": 2}, {"depth": True}, {"required_files": ("README.md",), "sources": (), "closed": False},
    {"sources": ()}, {"sources": (), "required_files": ("voice/output.py", "voice/OUTPUT.py"), "closed": False},
])
def test_support_closure_is_bounded_and_explicit(declared, changes):
    _, scope, _ = declared
    with pytest.raises(ValueError):
        replace(scope.support, **changes)


def test_missing_support_cannot_claim_complete_or_verified_findings(declared):
    _, scope, edge = declared
    scope = replace(scope, support=replace(scope.support, sources=(), closed=False))
    assert scope.support.missing_files == ("voice/output.py",)
    with pytest.raises(ValueError):
        complete(scope)
    coverage = ScopedCoverage(scope, inventory_files=scope.search_files, parsed_files=scope.search_files, inventory_complete=True)
    with pytest.raises(ValueError):
        ScopedRelationshipResult(coverage, Resolution.CONFIRMED_STATIC,
            CompletenessClaim.FINDINGS_ONLY, EvidenceSelection.COMPLETE, (edge,))


@pytest.mark.parametrize("reason", ["unreadable_python", "excluded_required_python", "invalid_python", "unsupported_python"])
def test_required_python_failures_remain_incomplete(declared, reason):
    _, scope, _ = declared
    coverage = ScopedCoverage(scope, inventory_files=scope.search_files, inventory_complete=True,
                              limitations=(FileDiagnostic("commands/run.py", reason),))
    assert coverage.status == CoverageStatus.INCOMPLETE
    with pytest.raises(ValueError):
        replace(coverage, status=CoverageStatus.COMPLETE)
    with pytest.raises(ValueError):
        replace(coverage, non_python_files=("commands/run.py",))
    with pytest.raises(ValueError):
        replace(coverage, parsed_files=scope.search_files)


def test_incomplete_inventory_and_extraction_cannot_be_hidden(declared):
    _, scope, edge = declared
    coverage = ScopedCoverage(scope, inventory_files=scope.search_files, parsed_files=scope.search_files,
                              inventory_complete=True, extraction_truncated=True)
    for claim in (CompletenessClaim.SCOPED_COMPLETE, CompletenessClaim.PROJECT_COMPLETE):
        with pytest.raises(ValueError):
            ScopedRelationshipResult(coverage, Resolution.CONFIRMED_STATIC, claim, EvidenceSelection.COMPLETE, (edge,))
    directory = replace(scope, kind=ScopeKind.DIRECTORY, roots=("commands",))
    with pytest.raises(ValueError):
        ScopedCoverage(directory, CoverageStatus.COMPLETE,
            inventory_files=("commands/run.py", "commands/new.py"), parsed_files=directory.search_files,
            inventory_complete=True)


@pytest.mark.parametrize("field,value", [
    ("evidence", EvidenceSelection.TRUNCATED), ("evidence", EvidenceSelection.UNAVAILABLE),
    ("resolution", Resolution.UNRESOLVED), ("resolution", Resolution.AMBIGUOUS),
    ("publication", PublicationEligibility.ELIGIBLE), ("publication", "disabled"),
])
def test_contradictory_claims_or_publication_flags_are_rejected(declared, field, value):
    _, scope, edge = declared
    result = ScopedRelationshipResult(complete(scope), Resolution.CONFIRMED_STATIC,
        CompletenessClaim.SCOPED_COMPLETE, EvidenceSelection.COMPLETE, (edge,))
    with pytest.raises(ValueError):
        replace(result, **{field: value})


def test_findings_are_nonexhaustive_and_never_publishable(declared):
    _, scope, edge = declared
    coverage = ScopedCoverage(scope, extraction_truncated=True)
    result = ScopedRelationshipResult(coverage, Resolution.INCOMPLETE,
        CompletenessClaim.FINDINGS_ONLY, EvidenceSelection.TRUNCATED, (edge,))
    assert not result.exhaustive and not result.publication_ready
    with pytest.raises(ValueError):
        replace(result, claim=CompletenessClaim.SCOPED_COMPLETE)
    with pytest.raises(ValueError):
        replace(result, relationships=())
    with pytest.raises(ValueError):
        replace(result, evidence=EvidenceSelection.UNAVAILABLE)


def test_relationship_provenance_and_direct_endpoint_cannot_escape(declared):
    _, scope, edge = declared
    result = ScopedRelationshipResult(complete(scope), Resolution.CONFIRMED_STATIC,
        CompletenessClaim.SCOPED_COMPLETE, EvidenceSelection.COMPLETE, (edge,))
    with pytest.raises(ValueError):
        replace(result, relationships=(edge, edge))
    with pytest.raises(ValueError):
        replace(result, relationships=(replace(edge, target=replace(edge.target, qualified_name="other")),))
    with pytest.raises(ValueError):
        replace(result, relationships=(replace(edge, target=replace(edge.target,
            definition=replace(edge.target.definition, digest="b" * 64))),))


def test_confirmed_resolution_cannot_hide_unresolved_record(declared):
    _, scope, edge = declared
    unknown = replace(edge, target=None, resolution=Resolution.UNRESOLVED)
    with pytest.raises(ValueError):
        ScopedRelationshipResult(ScopedCoverage(scope), Resolution.CONFIRMED_STATIC,
            CompletenessClaim.NONE, EvidenceSelection.UNAVAILABLE, (unknown,))


def test_forward_complete_query_requires_target_in_search_domain(declared):
    _, scope, _ = declared
    forward = replace(scope, direction="forward")
    with pytest.raises(ValueError):
        ScopedRelationshipResult(complete(forward), Resolution.CONFIRMED_STATIC,
            CompletenessClaim.SCOPED_COMPLETE, EvidenceSelection.COMPLETE)


def test_directory_exclusion_does_not_admit_case_alias(declared):
    _, scope, _ = declared
    with pytest.raises(ValueError):
        replace(scope, kind=ScopeKind.DIRECTORY, roots=("commands",),
                excluded_paths=("commands/RUN.py",))


def test_transitive_and_cancelled_results_cannot_claim_initial_complete_mode(declared):
    _, scope, edge = declared
    scope = replace(scope, semantics=QuerySemantics.TRANSITIVE)
    with pytest.raises(ValueError):
        ScopedRelationshipResult(complete(scope), Resolution.CONFIRMED_STATIC,
            CompletenessClaim.SCOPED_COMPLETE, EvidenceSelection.COMPLETE, (edge,))
    cancelled = replace(complete(scope), status=CoverageStatus.CANCELLED)
    with pytest.raises(ValueError):
        ScopedRelationshipResult(cancelled, Resolution.CONFIRMED_STATIC,
            CompletenessClaim.FINDINGS_ONLY, EvidenceSelection.COMPLETE, (edge,))


@pytest.mark.parametrize("path", ["data/hidden.py", ".codex/source.py", "credentials.py"])
def test_scope_admission_keeps_c1_exclusions(declared, path):
    request, scope, _ = declared
    forbidden = replace(scope, roots=(path,), search_files=(path,))
    with pytest.raises(access.ProjectAccessError):
        request.validate_scope(forbidden)


def test_authorization_revocation_switching_and_cancellation_are_preserved(declared, tmp_path):
    request, scope, _ = declared
    event = threading.Event()
    cancellable = AnalysisRequest.capture(cancellation_event=event)
    event.set()
    with pytest.raises(OperationCancelled):
        cancellable.validate_scope(scope)
    access.register_project("other", tmp_path)
    access.select_project("other")
    with pytest.raises(access.ProjectAccessError):
        request.validate_scope(scope)
    access.select_project("c3")
    access.revoke_project("c3")
    with pytest.raises(access.ProjectAccessError):
        request.validate_scope(scope)


def test_c2_snapshot_coverage_and_budgets_are_unchanged(declared):
    request, scope, _ = declared
    coverage = AnalysisCoverage(discovered=("README.md",), unsupported=(FileDiagnostic("README.md", "unsupported_source_language"),),
                                discovery_complete=True)
    assert not coverage.complete
    snapshot = AnalysisSnapshot(request.identity, coverage)
    before = snapshot.snapshot_id
    request.validate_scope(scope)
    assert snapshot.snapshot_id == before and snapshot.schema_version == "c2.1"
    assert AnalysisLimits().seconds == 5 and AnalysisLimits().relationships == 10000
