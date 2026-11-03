"""Independent C3 proof replay and check-time eligibility; no delivery integration.

Candidates, fingerprints, citations and coverage declarations are untrusted.
Reconstruct binding proofs from full safe source reads, using the C2 lexical
primitives (never the C3 analyzer's verified labels). Excerpts are only display
windows. The original request pays for replay, evidence and final freshness.
"""
import ast
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

from models.project_relationships import (
    SourceFingerprint, SourceLocation, Resolution, RelationshipKind, SymbolKind,
)
from models.project_scope import (
    AnalysisScope, CompletenessClaim, ScopeKind, QuerySemantics, CoverageStatus,
    EvidenceSelection, PublicationEligibility,
)
from models.scoped_validation import ScopedCallerEvidence, ScopedValidationOutcome
from models.relationship_answer import EvidenceSupport, excerpt_identity
from models.source_evidence import RetrievalLimits, RetrievalStatus
from services.cancellation import OperationCancelled
from services.project_access import ProjectAccessError
from services.project_analysis_request import AnalysisRequest, AnalysisBudgetExceeded, AnalysisLimits
from services.project_analysis_cache import read_analysis_source
from services.project_retrieval import discover
from services.project_symbol_index import extract_scoped_symbols
from services.project_dependencies import resolve_source_import
from services.project_execution import resolve_source_calls
from services.project_target import resolve_analysis_target
from services.project_relationship_evidence import _range_for
from services.scoped_relationship_analysis import ScopedCallerAnalysis


class ScopedValidationError(ValueError):
    def __init__(self, reason, stage="evidence"):
        self.reason, self.stage = reason, stage
        super().__init__(reason)


_CLAIMS = {CompletenessClaim.FINDINGS_ONLY, CompletenessClaim.SCOPED_COMPLETE,
           CompletenessClaim.PROJECT_COMPLETE}


def _require(condition, reason, stage="evidence"):
    if not condition:
        raise ScopedValidationError(reason, stage)


def _inventory(scope, request):
    excluded = []
    listing = discover(request.context, analysis_request=request, exclusion_diagnostics=excluded,
        limits=replace(RetrievalLimits(), seconds=request.budget.limits.seconds))
    request.check_authorization()  # propagates cancellation/deadline hidden by retrieval
    _require(listing.status == RetrievalStatus.SUCCESS, "inventory_unavailable", "freshness")
    paths = tuple(sorted(p for p in listing.paths if p.lower().endswith(".py")))
    return paths, tuple(sorted(excluded))


def _binding_inventory(observation, inventory, excluded):
    """An excluded module/package alternative is unknown, never nonexistent.

    Feed matching denied alternatives to the resolver so require_all_candidates
    refuses their missing proof. No excluded source is opened or admitted.
    """
    node, alias = observation.node, observation.alias_node
    name = node.module or "" if isinstance(node, ast.ImportFrom) else alias.name
    if isinstance(node, ast.ImportFrom) and node.level:
        package = observation.source.excerpt.path.split("/")[:-1]
        if node.level > len(package):
            return set(inventory)
        name = ".".join(package[:len(package) - node.level + 1] + ([name] if name else []))
    stem = name.replace(".", "/")
    stems = [stem]
    if isinstance(node, ast.ImportFrom) and alias.name != "*":
        stems.append(stem + "/" + alias.name)
    candidates = [p for stem in stems for p in (stem + ".py", stem + "/__init__.py")]
    return set(inventory) | {p for p in candidates if any(
        p == path or p.startswith(path + "/") for path, _ in excluded)}


def _admit(candidate, scope, request, claim):
    _require(isinstance(request, AnalysisRequest), "invalid_request")
    request.check_authorization()
    _require(isinstance(scope, AnalysisScope) and isinstance(candidate, ScopedCallerAnalysis), "invalid_candidate")
    _require(isinstance(claim, CompletenessClaim) and claim in _CLAIMS, "unsupported_claim")
    # Caller owns this declaration; never take the scope to authorize from a candidate.
    request.validate_scope(scope)
    _require(scope.operation == RelationshipKind.CALLS and scope.direction == "reverse"
             and scope.semantics == QuerySemantics.DIRECT, "unsupported_query")
    if claim == CompletenessClaim.PROJECT_COMPLETE:
        _require(scope.kind == ScopeKind.PROJECT_PYTHON and not scope.excluded_paths,
                 "narrowed_project_claim", "completeness")
    limits = request.budget.limits
    defaults = AnalysisLimits()
    # Validate collection bounds before traversing any supplied nested records.
    _require(type(candidate.result.relationships) is tuple
             and len(candidate.result.relationships) <= min(defaults.relationships, limits.relationships)
             and type(candidate.fingerprints) is tuple
             and len(candidate.fingerprints) <= min(defaults.python_files, limits.python_files)
             and type(candidate.source_inventory) is tuple and len(candidate.source_inventory) <= 10000
             and type(candidate.inventory_exclusions) is tuple and len(candidate.inventory_exclusions) <= 10000,
             "candidate_resource_limit")
    provenance_count = 0
    for edge in candidate.result.relationships:
        request.budget.check()
        _require(type(edge.supporting_sources) is tuple and type(edge.candidates) is tuple,
                 "malformed_relationship_dependencies")
        provenance_count += 1 + len(edge.supporting_sources) + len(edge.candidates)
        _require(provenance_count <= min(defaults.relationships, limits.relationships),
                 "candidate_provenance_limit")
    _require(len(scope.search_files) + len(scope.support.required_files) <= min(defaults.python_files, limits.python_files),
             "proof_file_limit")
    actual_scope = candidate.result.coverage.scope
    _require(actual_scope == scope and candidate.scope_id == scope.scope_id, "scope_identity_changed")
    replace(scope)
    replace(scope.support)
    replace(candidate.result.coverage)
    replace(candidate.result)
    _require(candidate.result.publication == PublicationEligibility.DISABLED, "publication_already_enabled")
    _require(candidate.result.claim in {CompletenessClaim.NONE, claim}, "contradictory_claim")
    _require(candidate.result.evidence != EvidenceSelection.TRUNCATED
             and not candidate.result.coverage.extraction_truncated
             and not any(d.startswith("budget:") for d in candidate.diagnostics), "analysis_or_selection_truncated")
    _require(not candidate.result.coverage.source_changed, "analysis_source_changed", "freshness")
    _require(candidate.target_status == "resolved" and candidate.target_candidates == (scope.target,),
             "target_not_exact")
    _require(scope.support.complete, "support_closure_incomplete")
    for edge in candidate.result.relationships:
        request.budget.check()
        replace(edge)
    return tuple(edge for edge in candidate.result.relationships if edge.resolution == Resolution.CONFIRMED_STATIC)


def _replay(candidate, scope, request):
    inventory, excluded = _inventory(scope, request)
    _require((inventory, excluded) == (candidate.source_inventory, candidate.inventory_exclusions),
             "source_inventory_changed", "freshness")
    membership = tuple(p for p in inventory if scope.contains(p))
    _require(membership == scope.search_files, "search_membership_changed", "freshness")
    _require(candidate.result.coverage.inventory_files == membership, "contradictory_search_coverage")
    sources, modules = {}, {}
    paths = tuple(sorted(scope.search_files + scope.support.required_files))
    fingerprints = candidate.fingerprints
    _require(all(isinstance(f, SourceFingerprint) for f in fingerprints)
             and tuple(f.path for f in fingerprints) == paths, "missing_or_extra_proof_dependencies")
    expected_digests = {f.path: f.digest for f in fingerprints}
    for path in paths:
        request.check_authorization()
        request.budget.consume(python_files=1)
        fresh = read_analysis_source(request, path)
        request.budget.check()
        _require(fresh.success and fresh.excerpts and not fresh.excerpts[0].truncated,
                 "proof_source_unavailable:" + path)
        source = fresh.excerpts[0]
        _require(source.digest == expected_digests[path], "source_digest_changed:" + path, "freshness")
        sources[path] = source
        tree = ast.parse(source.text, filename=path)
        count = 0
        for _ in ast.walk(tree):
            count += 1
            request.budget.consume(ast_nodes=1)
            request.budget.check_file(fresh.bytes_read, count)
        modules[path] = extract_scoped_symbols(tree, source, request)
    for expected in scope.support.sources:
        _require(expected == SourceLocation.from_excerpt(request.identity, sources[expected.path]),
                 "support_source_changed", "freshness")
    symbols = tuple(s.symbol for m in modules.values() for s in m.scopes)
    selected = resolve_analysis_target(SimpleNamespace(symbols=symbols),
        filename="./" + scope.target.definition.path, qualified_name=scope.target.qualified_name)
    _require(selected["status"] == "resolved" and selected["target"] == scope.target, "target_identity_unproven")
    target = next(s for m in modules.values() for s in m.scopes if s.symbol == scope.target)
    _require(scope.target.kind in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD}
             and not target.conditional
             and (scope.target.kind == SymbolKind.METHOD or not getattr(target.node, "decorator_list", ())),
             "unsupported_target_binding")
    bindings, support_dependencies = {}, set()
    for path, module in sorted(modules.items()):
        for observation in module.imports:
            request.budget.consume(relationships=1)
            edge, binding = resolve_source_import(observation, modules, _binding_inventory(observation, inventory, excluded),
                inventory_complete=True, require_all_candidates=True)
            _require(edge.reason != "module_not_analyzed", "missing_module_candidate_dependency")
            bindings[id(observation)] = edge, binding
            if binding is not None and path in scope.support.required_files:
                support_dependencies.add(binding.symbol.definition.path)
    _require(not support_dependencies - set(scope.search_files) - {scope.target.definition.path},
             "support_depth_boundary")
    tainted = {binding.symbol.definition.path for module in modules.values()
               for observation in module.imports for _, binding in [bindings[id(observation)]]
               if binding is not None and observation.bound_name in module.mutations}
    verified, boundaries = [], []
    for path in scope.search_files:
        for edge in resolve_source_calls(modules[path], modules, bindings, request, tainted_paths=tainted):
            if edge.resolution == Resolution.CONFIRMED_STATIC:
                if edge.target == scope.target:
                    verified.append(edge)
            else:
                boundaries.append(edge)
    canonical = tuple(sorted(verified + boundaries, key=lambda e:
        (e.location.path, e.location.start_line, e.location.start_column, e.relationship_id)))
    _require(candidate.result.relationships == canonical, "relationship_proof_mismatch_or_omission")
    coverage = candidate.result.coverage
    _require(coverage.parsed_files == scope.search_files and not coverage.limitations
             and coverage.inventory_complete and coverage.status == CoverageStatus.COMPLETE,
             "coverage_proof_incomplete", "completeness")
    resolution = (Resolution.AMBIGUOUS if any(e.resolution == Resolution.AMBIGUOUS for e in boundaries) else
                  Resolution.UNRESOLVED if boundaries else Resolution.CONFIRMED_STATIC)
    _require(candidate.result.resolution == resolution, "contradictory_resolution_metadata")
    excluded_relevant = any(scope._included(path) and not any(
        path == p or path.startswith(p + "/") for p in scope.excluded_paths) for path, _ in excluded)
    return sources, tuple(verified), not boundaries and not excluded_relevant


def _select_evidence(scope, request, claim, sources, verified):
    _require(len(verified) <= min(32, request.budget.limits.selected_relationships), "evidence_relationship_limit")
    request.budget.consume(selected_relationships=len(verified))
    specs = [(None, scope.target.symbol_id, "header", scope.target.definition)]
    symbols = {scope.target.symbol_id: scope.target}
    for edge in verified:
        request.budget.check()
        symbols[edge.origin.symbol_id] = edge.origin
        specs.extend([(edge.relationship_id, None, "site", edge.location),
                      (edge.relationship_id, edge.origin.symbol_id, "header", edge.origin.definition)])
        specs.extend((edge.relationship_id, None, "binding", source) for source in edge.supporting_sources)
    _require(len(specs) <= 256, "evidence_support_limit")
    display_paths = {spec[3].path for spec in specs}
    _require(len(display_paths) <= min(6, request.budget.limits.evidence_files), "evidence_file_limit")
    request.budget.consume(evidence_files=len(display_paths))
    planned, ranges = [], {}
    for spec in specs:
        request.budget.check()
        source = sources[spec[3].path]
        start, end = _range_for(spec, source.text, 1, symbols)
        _require(end - start + 1 <= 120, "evidence_range_limit")
        planned.append((spec, start, end))
        ranges.setdefault(source.path, set()).add((start, end))
    excerpts = []
    for path, windows in sorted(ranges.items()):
        merged = []
        for start, end in sorted(windows):
            if merged and start <= merged[-1][1] + 1 and max(end, merged[-1][1]) - merged[-1][0] + 1 <= 120:
                merged[-1] = merged[-1][0], max(end, merged[-1][1])
            else:
                merged.append((start, end))
        for start, end in merged:
            source = sources[path]
            excerpts.append(replace(source, source_id=excerpt_identity(scope.scope_id, path, start, end, source.digest),
                start_line=start, end_line=end, text="\n".join(source.text.split("\n")[start-1:end]),
                truncated=start > 1 or end < source.total_lines))
    _require(len(excerpts) <= min(8, request.budget.limits.evidence_excerpts), "evidence_excerpt_limit")
    _require(sum(len(e.text.encode("utf-8")) for e in excerpts) < 12 * 1024, "evidence_text_limit")
    request.budget.consume(evidence_excerpts=len(excerpts))
    supports = []
    for spec, start, end in planned:
        excerpt = next(e for e in excerpts if e.path == spec[3].path and e.start_line <= start <= end <= e.end_line)
        supports.append(EvidenceSupport(*spec[:3], spec[3], start, end, excerpt.source_id))
    return tuple(excerpts), tuple(supports)


def _prepare(candidate, scope, request, claim):
    _admit(candidate, scope, request, claim)
    sources, verified, complete = _replay(candidate, scope, request)
    if claim == CompletenessClaim.FINDINGS_ONLY:
        _require(bool(verified), "no_verified_findings")
    else:
        _require(complete and candidate.result.resolution == Resolution.CONFIRMED_STATIC,
                 "relevant_unresolved_boundaries", "completeness")
    excerpts, supports = _select_evidence(scope, request, claim, sources, verified)
    packet = ScopedCallerEvidence(scope.scope_id, claim, tuple(e.relationship_id for e in verified),
        candidate.fingerprints, candidate.source_inventory, candidate.inventory_exclusions, excerpts, supports)
    _require(len(json.dumps(asdict(packet), separators=(",", ":")).encode("utf-8"))
             <= min(24 * 1024, request.budget.limits.payload_bytes), "evidence_payload_limit")
    return packet


def collect_scoped_caller_evidence(candidate, expected_scope, request, *, claim=CompletenessClaim.FINDINGS_ONLY):
    """Build bounded display evidence after proof replay; not an eligibility grant.

    Errors/cancellation propagate. A separately supplied packet will be rebuilt
    and checked again by validate_scoped_callers, using the same request budget.
    """
    return _prepare(candidate, expected_scope, request, claim)


def _check_packet(supplied, expected, request):
    _require(type(supplied) is ScopedCallerEvidence, "invalid_evidence_packet")
    _require(all(type(getattr(supplied, name)) is tuple for name in (
        "excerpts", "supports", "proof_dependencies", "relationship_ids", "source_inventory", "inventory_exclusions")),
        "invalid_evidence_collections")
    _require(len(supplied.excerpts) <= 8 and len(supplied.supports) <= 256
             and len(supplied.proof_dependencies) <= 256 and len(supplied.relationship_ids) <= 32,
             "evidence_selection_truncated_or_oversized")
    _require(len(supplied.source_inventory) <= 10000 and len(supplied.inventory_exclusions) <= 10000
             and sum(len(e.text) for e in supplied.excerpts) < 12 * 1024
             and sum(len(e.text.encode("utf-8")) for e in supplied.excerpts) < 12 * 1024,
             "evidence_payload_limit")
    # Retrieval time is descriptive. Every other citation attribute is canonical.
    request.budget.check()
    _require(replace(supplied, excerpts=(), supports=()) == replace(expected, excerpts=(), supports=())
             and supplied.supports == expected.supports
             and tuple(replace(e, retrieved_at="") for e in supplied.excerpts)
             == tuple(replace(e, retrieved_at="") for e in expected.excerpts),
             "fabricated_or_incomplete_evidence")


def _final_freshness(candidate, scope, request):
    # Reserve a final pass, never a renewed request/deadline or partial grant.
    _require(request.budget.remaining_seconds >= 0.05, "insufficient_freshness_reservation", "freshness")
    expected = candidate.source_inventory, candidate.inventory_exclusions
    _require(_inventory(scope, request) == expected, "source_inventory_changed", "freshness")
    for fingerprint in candidate.fingerprints:
        request.check_authorization()
        read = read_analysis_source(request, fingerprint.path)
        request.budget.check()
        _require(read.success and read.excerpts and not read.excerpts[0].truncated
                 and read.excerpts[0].digest == fingerprint.digest,
                 "proof_dependency_changed:" + fingerprint.path, "freshness")
    _require(_inventory(scope, request) == expected, "source_inventory_changed", "freshness")
    request.check_authorization()


def validate_scoped_callers(candidate, expected_scope, request, *,
                            claim=CompletenessClaim.FINDINGS_ONLY, evidence=None):
    """Return a fail-closed, check-time outcome. Never speak, persist or publish.

    expected_scope must come from the caller's captured declaration, not from
    an untrusted result. Eligibility is advisory internal metadata; source can
    change after this check and future delivery will require another check.
    """
    scope_id = expected_scope.scope_id if isinstance(expected_scope, AnalysisScope) else ""
    mode = claim if isinstance(claim, CompletenessClaim) else None
    def refusal(reason, stage="evidence", state="refused"):
        statuses = {"evidence_status": "unverified", "freshness_status": "unverified",
                    "authorization_status": "unverified", "completeness_status": "unverified"}
        statuses[stage + "_status"] = state
        return ScopedValidationOutcome(scope_id, mode, refusal_reasons=(reason,), **statuses)
    try:
        packet = _prepare(candidate, expected_scope, request, claim)
        if evidence is not None:
            _check_packet(evidence, packet, request)
        _final_freshness(candidate, expected_scope, request)
        return ScopedValidationOutcome(scope_id, claim, "verified", "verified", "verified",
            "not_claimed" if claim == CompletenessClaim.FINDINGS_ONLY else "complete",
            publication_eligible=True, evidence=packet)
    except OperationCancelled:
        return refusal("validation_cancelled", "freshness", "cancelled")
    except AnalysisBudgetExceeded as exc:
        return refusal("validation_budget_exhausted:" + exc.resource, "freshness")
    except ProjectAccessError:
        return refusal("project_authorization_or_containment_changed", "authorization", "refused")
    except ScopedValidationError as exc:
        return refusal(exc.reason, exc.stage)
    except (ValueError, TypeError, AttributeError, KeyError, IndexError, SyntaxError, RecursionError, OSError):
        return refusal("malformed_or_unverifiable_provenance")
