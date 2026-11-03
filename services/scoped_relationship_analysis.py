"""Internal C3 direct callers. No routing, response rendering, or publication.

Scope membership is a declaration to verify, never permission to expand a query.
Only declared files are read, with the existing C1 safe reader. All inventory,
parse, import, candidate-call and verification work shares the original budget.
"""
import ast
from dataclasses import dataclass, replace

from models.project_relationships import (
    RelationshipKind, RelationshipRecord, Resolution, SourceFingerprint, SourceLocation,
    SymbolRecord, SymbolKind, FileDiagnostic,
)
from models.project_scope import (
    AnalysisScope, SupportClosure, ScopedCoverage, ScopedRelationshipResult,
    ScopeKind, QuerySemantics, CoverageStatus, CompletenessClaim, EvidenceSelection,
)
from models.source_evidence import RetrievalLimits, RetrievalStatus
from services.project_analysis_request import AnalysisRequest, AnalysisBudgetExceeded, BudgetUsage
from services.project_access import ProjectAccessError
from services.project_access import validate_project, get_project
from services.project_retrieval import discover, permitted
from services.project_analysis_cache import read_analysis_source
from services.project_symbol_index import extract_scoped_symbols
from services.project_dependencies import resolve_source_import
from services.project_execution import resolve_source_calls
from services.project_target import resolve_analysis_target


@dataclass(frozen=True)
class ScopedCallerAnalysis:
    result: ScopedRelationshipResult
    target_status: str
    target_candidates: tuple[SymbolRecord, ...]
    fingerprints: tuple[SourceFingerprint, ...]
    diagnostics: tuple[str, ...]
    usage: BudgetUsage

    @property
    def scope_id(self):
        return self.result.coverage.scope.scope_id

    @property
    def verified_callers(self):
        return tuple(edge for edge in self.result.relationships if edge.resolution == Resolution.CONFIRMED_STATIC)

    @property
    def boundaries(self):
        return tuple(edge for edge in self.result.relationships if edge.resolution != Resolution.CONFIRMED_STATIC)

    @property
    def publication_ready(self):
        return False

    @property
    def freshness_verified(self):
        # Consistency re-reads below do not constitute a publication certificate.
        return False


@dataclass(frozen=True)
class _SymbolCatalog:
    # Existing exact target resolver consumes this same symbols interface.
    symbols: tuple[SymbolRecord, ...]


def analyze_scoped_callers(scope, request):
    """Analyze exact direct static callers under a captured C3 scope/request.

    Unsupported operations and authorization failures raise. Missing/ambiguous/
    changed targets, policy-denied required inputs and bounded incomplete work
    return internal diagnostics. Cancellation always propagates; no partial
    results are delivered after revocation or project switching.
    """
    if not isinstance(scope, AnalysisScope) or not isinstance(request, AnalysisRequest):
        raise ValueError("Expected a C3 scope and captured analysis request.")
    if (scope.operation != RelationshipKind.CALLS or scope.direction != "reverse"
            or scope.semantics != QuerySemantics.DIRECT):
        raise ValueError("C3.3 supports reverse direct static calls only.")
    policy_denied = False
    try:
        request.validate_scope(scope)
    except ProjectAccessError:
        # A policy-denied declaration may return diagnostic-only coverage, but
        # an unauthorized/stale root must never be admitted by this branch.
        request.check_authorization()
        if scope.project != request.identity:
            raise
        policy_denied = any(not permitted(p) for p in scope.search_files + scope.support.required_files)
        policy_denied |= scope.kind == ScopeKind.DIRECTORY and any(
            not permitted(root + "/scope_probe.py") for root in scope.roots)
        if not policy_denied:
            raise

    modules, excerpts, bindings, edges = {}, {}, {}, []
    inventory, non_python, failures, diagnostics = (), (), {}, set()
    discovery_complete = False
    extraction_truncated = False
    source_changed = False
    target_status, target_candidates = "not_found", ()
    support_closed = False
    parsed = set()

    def listing():
        return discover(request.context, analysis_request=request,
                        limits=replace(RetrievalLimits(), seconds=request.budget.limits.seconds))

    def check_active():
        # Time exhaustion may return internal partial work, but never masks
        # cancellation, revocation, or an active-project change.
        try:
            request.check_authorization()
        except AnalysisBudgetExceeded as exc:
            validate_project(request.context)
            if request.context != get_project():
                raise ProjectAccessError("Active project changed during scoped analysis.")
            try:
                request.budget.check()
            except AnalysisBudgetExceeded:
                pass
            return exc.resource
        return None

    try:
        if policy_denied:
            diagnostics.add("source_policy_exclusion")
            for path in scope.search_files + scope.support.required_files:
                if not permitted(path):
                    failures[path] = "excluded_required_python"
        else:
            found = listing()
            request.budget.check()  # includes cancellation returned by discovery
            discovery_complete = found.status == RetrievalStatus.SUCCESS
            if not discovery_complete:
                diagnostics.add("inventory_incomplete")
            inventory = tuple(sorted(p for p in found.paths if scope.contains(p)))
            non_python = tuple(sorted(p for p in found.paths if scope._included(p)
                                     and not p.lower().endswith(".py")))
            if set(inventory) != set(scope.search_files):
                diagnostics.add("search_membership_changed")
            # The inventory can reveal new search files, but never admits them
            # into the declared plan or silently reads them as support.
            for path in sorted(set(scope.search_files) | set(scope.support.required_files)):
                request.check_authorization()
                request.budget.consume(python_files=1)
                read = read_analysis_source(request, path)
                request.budget.check()
                if not read.success or not read.excerpts or read.excerpts[0].truncated:
                    diagnostics.update("read_limit:" + reason for reason in read.limits_reached)
                    failures[path] = "excluded_required_python" if read.status == RetrievalStatus.DENIED else "unreadable_python"
                    resources = [r.removeprefix("analysis:") for r in read.limits_reached if r.startswith("analysis:")]
                    if resources:
                        raise AnalysisBudgetExceeded(resources[0])
                    continue
                excerpt = read.excerpts[0]
                excerpts[path] = excerpt
                if path in scope.search_files and path not in inventory:
                    failures[path] = "unreadable_python"
                    diagnostics.add("search_membership_changed")
                    continue
                try:
                    tree = ast.parse(excerpt.text, filename=path)
                    count = 0
                    for _ in ast.walk(tree):
                        count += 1
                        request.budget.consume(ast_nodes=1)
                        request.budget.check_file(read.bytes_read, count)
                    modules[path] = extract_scoped_symbols(tree, excerpt, request)
                except (SyntaxError, RecursionError, ValueError):
                    failures[path] = "invalid_python"
                    continue
                parsed.add(path)

            symbols = tuple(s.symbol for module in modules.values() for s in module.scopes)
            selected = resolve_analysis_target(_SymbolCatalog(symbols),
                filename="./" + scope.target.definition.path, qualified_name=scope.target.qualified_name)
            target_status, target_candidates = selected["status"], selected["candidates"]
            if target_status == "resolved":
                if selected["target"] != scope.target:
                    target_status, source_changed = "stale", True
                    diagnostics.add("target_snapshot_changed")
                elif scope.target.kind not in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD}:
                    target_status = "unsupported"
                else:
                    target_scope = next(s for m in modules.values() for s in m.scopes if s.symbol == scope.target)
                    if target_scope.conditional or (scope.target.kind != SymbolKind.METHOD
                                                   and getattr(target_scope.node, "decorator_list", ())):
                        target_status = "unsupported"

            # Import/binding records are bounded working data, not a project graph.
            # Support call bodies are indexed for mutation safeguards but never
            # extracted as caller candidates.
            support_dependencies = set()
            available_paths = set(found.paths)
            for path, module in sorted(modules.items()):
                for observation in module.imports:
                    request.check_authorization()
                    request.budget.consume(relationships=1)
                    edge, binding = resolve_source_import(observation, modules, available_paths,
                        inventory_complete=discovery_complete, require_all_candidates=True)
                    bindings[id(observation)] = edge, binding
                    if edge.reason == "module_not_analyzed":
                        diagnostics.add("undeclared_or_unavailable_support")
                    if binding is not None and path in scope.support.required_files:
                        support_dependencies.add(binding.symbol.definition.path)
            if support_dependencies - set(scope.search_files) - {scope.target.definition.path}:
                diagnostics.add("support_depth_boundary")
            support_closed = (set(scope.support.required_files) <= parsed
                              and "undeclared_or_unavailable_support" not in diagnostics
                              and "support_depth_boundary" not in diagnostics)
            tainted = {binding.symbol.definition.path for module in modules.values()
                       for observation in module.imports for _, binding in [bindings[id(observation)]]
                       if binding is not None and observation.bound_name in module.mutations}
            if target_status == "resolved":
                for path in sorted(set(scope.search_files) & parsed):
                    for edge in resolve_source_calls(modules[path], modules, bindings, request, tainted_paths=tainted):
                        request.check_authorization()
                        if edge.resolution == Resolution.CONFIRMED_STATIC:
                            if edge.target.symbol_id != scope.target.symbol_id:
                                continue
                            if not support_closed:
                                edge = replace(edge, target=None, resolution=Resolution.INCOMPLETE,
                                               reason="support_closure_incomplete")
                        edges.append(edge)

            # Detect changes during analysis, without claiming publication
            # freshness. These actual reads use the same source-byte/deadline budget.
            for path, excerpt in sorted(excerpts.items()):
                read = read_analysis_source(request, path)
                request.budget.check()
                if not read.success or not read.excerpts or read.excerpts[0].digest != excerpt.digest:
                    source_changed = True
            second = listing()
            request.budget.check()
            if (second.status != RetrievalStatus.SUCCESS or
                    {p for p in second.paths if p.lower().endswith(".py")} !=
                    {p for p in found.paths if p.lower().endswith(".py")}):
                # A new module/package alternative outside caller scope can
                # invalidate a binding just as a new caller can change coverage.
                source_changed = True
            if source_changed:
                diagnostics.add("source_or_inventory_changed")
                edges.clear()
    except AnalysisBudgetExceeded as exc:
        diagnostics.add("budget:" + exc.resource)
        extraction_truncated = True

    # Budget exhaustion may produce internal partial work; cancellation and
    # authorization checks still apply and cannot be swallowed by that outcome.
    exhausted = check_active()
    if exhausted:
        diagnostics.add("budget:" + exhausted)
        extraction_truncated = True
    for path in scope.search_files + scope.support.required_files:
        if path not in parsed and path not in failures:
            failures[path] = "unreadable_python"
    if target_status != "resolved":
        edges.clear()
    # Declared support fingerprints are expectations. They cannot be silently
    # replaced with different source while retaining candidates from the old plan.
    for expected in scope.support.sources:
        actual = excerpts.get(expected.path)
        if actual and (actual.digest != expected.digest or actual.source_id != expected.source_id):
            source_changed = True
            diagnostics.add("support_snapshot_changed")
            edges.clear()
    sources = (() if source_changed else tuple(SourceLocation.from_excerpt(request.identity, excerpts[p])
                    for p in scope.support.required_files if p in parsed))
    updated_support = SupportClosure(scope.project, scope.support.required_files, sources,
        closed=support_closed and not source_changed and not extraction_truncated,
        depth=1 if scope.support.required_files else 0)
    effective_scope = replace(scope, support=updated_support)
    complete = (discovery_complete and not extraction_truncated and not source_changed and not failures
                and updated_support.complete and set(inventory) == set(scope.search_files)
                and set(scope.search_files) <= parsed)
    coverage = ScopedCoverage(effective_scope, CoverageStatus.COMPLETE if complete else CoverageStatus.INCOMPLETE,
        inventory_files=inventory, parsed_files=tuple(sorted(parsed & set(scope.search_files))),
        inventory_complete=discovery_complete, extraction_truncated=extraction_truncated,
        limitations=tuple(FileDiagnostic(p, reason) for p, reason in sorted(failures.items())),
        non_python_files=non_python, source_changed=source_changed)
    resolution = (Resolution.INCOMPLETE if not complete or target_status != "resolved" else
                  Resolution.AMBIGUOUS if any(e.resolution == Resolution.AMBIGUOUS for e in edges) else
                  Resolution.UNRESOLVED if any(e.resolution != Resolution.CONFIRMED_STATIC for e in edges) else
                  Resolution.CONFIRMED_STATIC)
    result = ScopedRelationshipResult(coverage, resolution, CompletenessClaim.NONE,
                                     EvidenceSelection.UNAVAILABLE, tuple(sorted(edges, key=lambda e:
                                     (e.location.path, e.location.start_line, e.location.start_column, e.relationship_id))))
    exhausted = check_active()
    if exhausted:
        diagnostics.add("budget:" + exhausted)
        result = replace(result, coverage=replace(coverage, status=CoverageStatus.INCOMPLETE,
            extraction_truncated=True), resolution=Resolution.INCOMPLETE)
    return ScopedCallerAnalysis(result, target_status, target_candidates,
        tuple(SourceFingerprint(p, e.digest) for p, e in sorted(excerpts.items())),
        tuple(sorted(diagnostics)), request.budget.usage)
