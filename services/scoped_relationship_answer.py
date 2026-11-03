"""C3.5a internal orchestration only. No live router/capability registration.

One captured request pays for declaration discovery, target/support admission,
C3.3 extraction, independent C3.4 validation and deterministic cited text.
This module has no delivery, conversation, speaker, UI or model dependency.
"""
import ast
from dataclasses import replace
import json
from types import SimpleNamespace

from models.project_scope import (
    AnalysisScope, SupportClosure, ScopeKind, QuerySemantics, CompletenessClaim, SUPPORT_MAX_FILES,
)
from models.project_relationships import SourceLocation, RelationshipKind, SymbolKind
from models.source_evidence import RetrievalLimits, RetrievalStatus
from models.scoped_answer import ScopedCallerAnswerCandidate, CallerSourceReference
from services.project_access import (
    get_project, list_projects, resolve_project_path, ProjectAccessError,
)
from services.project_analysis_request import AnalysisRequest, AnalysisBudgetExceeded
from services.project_retrieval import discover, permitted
from services.project_analysis_cache import read_analysis_source
from services.project_symbol_index import extract_scoped_symbols
from services.project_target import resolve_analysis_target
from services.scoped_relationship_analysis import analyze_scoped_callers
from services.scoped_relationship_validation import validate_scoped_callers
from services.scoped_relationship_request import parse_scoped_caller_request
from services.project_relationship_evidence import _label
from services.source_answer import validate_answer
from services.cancellation import OperationCancelled


class _Clarification(ValueError):
    def __init__(self, reason, text, options=()):
        self.reason, self.text, self.options = reason, text, options


class _Refusal(ValueError):
    pass


def _project(intent, request):
    request.check_authorization()
    if intent.project_qualifier:
        matches = [p for p in list_projects() if p.project_id.casefold() == intent.project_qualifier.casefold()]
        if len(matches) != 1:
            raise _Clarification("project_identity_unresolved",
                "Specify one registered project identity and select it explicitly before analysis.")
        if matches[0] != request.context or matches[0] != get_project():
            raise _Refusal("project_qualifier_does_not_match_active_authorization")


def _canonical_path(path, request, *, directory=False):
    if not isinstance(path, str) or not path:
        raise _Refusal("explicit_scope_path_required")
    relative = path.replace("\\", "/")
    if relative.startswith("./"):
        relative = relative[2:]
    if directory:
        relative = relative.rstrip("/")
    resolved = resolve_project_path(request.context, relative)
    if directory:
        if not resolved.is_dir() or not permitted(relative + "/scope_probe.py"):
            raise _Refusal("directory_scope_denied")
    elif not resolved.is_file() or not relative.lower().endswith(".py") or not permitted(relative):
        raise _Refusal("file_scope_denied")
    return resolved.relative_to(request.context.root).as_posix()


def _import_paths(observation, inventory):
    """Plan only direct inventory-backed support; binding proof stays in C3.4."""
    node, alias = observation.node, observation.alias_node
    name = (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
    if isinstance(node, ast.ImportFrom) and node.level:
        package = observation.source.excerpt.path.split("/")[:-1]
        if node.level > len(package):
            return set()
        name = ".".join(package[:len(package)-node.level+1] + ([name] if name else []))
    stem = name.replace(".", "/")
    stems = [stem]
    if isinstance(node, ast.ImportFrom) and alias.name != "*":
        stems.append(stem + "/" + alias.name)
    return {path for stem in stems for path in (stem + ".py", stem + "/__init__.py") if path in inventory}


def _construct_scope(intent, request, current_file):
    if intent.scope_kind is None:
        raise _Clarification("scope_required",
            "Specify the caller-search scope: a file, a directory, or the active authorized project.")
    if intent.current_file:
        if not isinstance(current_file, SourceLocation) or current_file.project != request.identity:
            raise _Clarification("current_file_required",
                "Specify the exact authorized file for 'this file'; no file context was assumed.")
        roots = (_canonical_path(current_file.path, request),)
    elif intent.scope_kind == ScopeKind.PROJECT_PYTHON:
        roots = ()
    else:
        roots = (_canonical_path(intent.scope_path, request, directory=intent.scope_kind == ScopeKind.DIRECTORY),)
    excluded = []
    listing = discover(request.context, analysis_request=request, exclusion_diagnostics=excluded,
        limits=replace(RetrievalLimits(), seconds=request.budget.limits.seconds))
    request.check_authorization()
    if listing.status != RetrievalStatus.SUCCESS:
        raise _Refusal("scope_inventory_incomplete")
    inventory = tuple(sorted(path for path in listing.paths if path.lower().endswith(".py")))
    if intent.scope_kind == ScopeKind.PROJECT_PYTHON:
        search = inventory
    elif intent.scope_kind == ScopeKind.FILES:
        search = roots
        if not set(search) <= set(inventory):
            raise _Refusal("search_file_not_in_authorized_inventory")
    else:
        search = tuple(path for path in inventory if any(
            path.casefold().startswith(root.casefold() + "/") for root in roots))
    if len(search) > min(256, request.budget.limits.python_files):
        raise _Refusal("scope_file_budget_exceeded")
    sources, modules = {}, {}

    def read(path):
        if path in modules:
            return
        request.check_authorization()
        request.budget.consume(python_files=1)
        result = read_analysis_source(request, path)
        request.budget.check()
        if not result.success or not result.excerpts or result.excerpts[0].truncated:
            raise _Refusal("scope_source_unavailable:" + path)
        excerpt = result.excerpts[0]
        try:
            tree = ast.parse(excerpt.text, filename=path)
        except (SyntaxError, RecursionError, ValueError):
            raise _Refusal("scope_source_parse_failed:" + path)
        count = 0
        for _ in ast.walk(tree):
            count += 1
            request.budget.consume(ast_nodes=1)
            request.budget.check_file(result.bytes_read, count)
        sources[path] = excerpt
        modules[path] = extract_scoped_symbols(tree, excerpt, request)

    for path in search:
        read(path)
    if intent.current_file and sources[current_file.path].digest != current_file.digest:
        raise _Refusal("current_file_context_stale")
    support = set()
    for module in tuple(modules.values()):
        for observation in module.imports:
            request.budget.consume(relationships=1)
            support.update(_import_paths(observation, inventory) - set(search))
            if len(support) > SUPPORT_MAX_FILES:
                raise _Refusal("support_file_limit")
    target_path = None
    if intent.filename:
        filename = intent.filename.replace("\\", "/")
        exact = filename.startswith("./") or "/" in filename
        filename = filename.removeprefix("./")
        matches = [path for path in inventory if (path == filename if exact else path.rsplit("/", 1)[-1] == filename)]
        if len(matches) != 1:
            raise _Clarification("target_file_unresolved", "Specify one exact project-relative target file.", tuple(matches[:32]))
        target_path = matches[0]
        if target_path not in search:
            support.add(target_path)
    if len(support) > SUPPORT_MAX_FILES:
        raise _Refusal("support_file_limit")
    for path in sorted(support):
        read(path)
    symbols = tuple(s.symbol for module in modules.values() for s in module.scopes)
    selected = resolve_analysis_target(SimpleNamespace(symbols=symbols),
        filename="./" + target_path if target_path else None, qualified_name=intent.qualified_name)
    request.check_authorization()
    if selected["status"] != "resolved":
        options = tuple("./" + s.definition.path + "::" + s.qualified_name for s in selected["candidates"][:32])
        raise _Clarification("target_identity_unresolved",
            "Specify an exact file.py::Qualified.name target within the declared scope or its direct support. "
            "This lookup does not establish absence from other or unread code.", options)
    target = selected["target"]
    if target.kind not in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD}:
        raise _Refusal("target_is_not_callable_definition")
    support_sources = tuple(SourceLocation.from_excerpt(request.identity, sources[path]) for path in sorted(support))
    scope = AnalysisScope(request.identity, intent.scope_kind, roots, search,
        SupportClosure(request.identity, tuple(sorted(support)), support_sources, True, 1 if support else 0),
        target, RelationshipKind.CALLS, "reverse", QuerySemantics.DIRECT)
    request.validate_scope(scope)
    return scope, sources, inventory, tuple(sorted(excluded))


def _render(intent, scope, candidate, outcome, request):
    replace(outcome)
    if not outcome.publication_eligible or outcome.scope_id != scope.scope_id or not outcome.evidence:
        raise _Refusal("validator_did_not_grant_eligibility")
    packet = outcome.evidence
    records = {r.relationship_id: r for r in candidate.verified_callers}
    if set(records) != set(packet.relationship_ids) or packet.claim != outcome.claim:
        raise _Refusal("validated_relationship_set_changed")
    target_label = _label(scope.target)
    if scope.kind == ScopeKind.PROJECT_PYTHON:
        domain = "the entire authorized project " + json.dumps(scope.project.project_id) + " (Python only)"
    else:
        domain = scope.kind.value + " " + ", ".join(json.dumps(root) for root in scope.roots) + " (Python only)"
        domain += " in authorized project " + json.dumps(scope.project.project_id)
    # Scope path mentions are metadata, never substitute evidence for a relationship.
    qualification = ("Verified direct static findings within " + domain + ". Additional callers may exist. "
        if outcome.claim == CompletenessClaim.FINDINGS_ONLY else
        "Complete direct static caller list within " + domain + ". Completeness applies only to this scope and policy. ")
    qualification += "Static source relationships do not establish runtime execution. "
    excerpts = {e.source_id: e for e in packet.excerpts}
    target_sources = tuple(dict.fromkeys(s.excerpt_id for s in packet.supports if s.symbol_id == scope.target.symbol_id))
    if not target_sources:
        raise _Refusal("target_citation_missing")
    paragraphs, references, edges = [], [], []
    for identity in packet.relationship_ids:
        request.check_authorization()
        edge = records[identity]
        citation_ids = tuple(dict.fromkeys([s.excerpt_id for s in packet.supports if s.relationship_id == identity]
                                          + list(target_sources)))
        if not citation_ids:
            raise _Refusal("caller_citation_missing")
        text = _label(edge.origin) + " directly calls " + target_label + ". "
        if not paragraphs:
            text = qualification + text
        paragraphs.append(text + " ".join("[" + source + "]" for source in citation_ids))
        edges.append(edge)
        references.extend(CallerSourceReference(identity, source, excerpts[source].path,
            excerpts[source].start_line, excerpts[source].end_line) for source in citation_ids)
    if not paragraphs:
        if outcome.claim == CompletenessClaim.FINDINGS_ONLY:
            raise _Refusal("empty_findings_only")
        paragraphs = [qualification + "No direct static callers of " + target_label + " were found within that scope. "
                      + " ".join("[" + source + "]" for source in target_sources)]
    text = validate_answer("\n\n".join(paragraphs), packet)
    if text is None or len(text.encode("utf-8")) > min(24 * 1024, request.budget.limits.payload_bytes):
        raise _Refusal("answer_citation_or_payload_validation_failed")
    request.check_authorization()
    return ScopedCallerAnswerCandidate("findings_only" if outcome.claim == CompletenessClaim.FINDINGS_ONLY else "complete",
        text, intent, scope, outcome, tuple(edges), tuple(references), analysis=candidate)


def prepare_scoped_caller_answer(command, request, *, current_file=None, claim=CompletenessClaim.SCOPED_COMPLETE):
    """Explicit internal dispatcher; no fallback, publication or state mutation.

    Missing/ambiguous intent yields clarification before C3 caller analysis.
    current_file, when supplied, must be an explicitly captured SourceLocation,
    not a guessed conversation topic. Cancellation propagates to its owner.
    """
    intent = parse_scoped_caller_request(command)
    scope, outcome = None, None
    try:
        if not isinstance(request, AnalysisRequest):
            raise _Refusal("captured_analysis_request_required")
        request.budget.check()
        if intent is None or not intent.direct:
            return ScopedCallerAnswerCandidate("not_applicable", "C3 supports direct static callers only.", intent)
        _project(intent, request)
        if intent.error:
            raise _Clarification(intent.error, "Specify an exact callable target and one explicit search scope.")
        if not isinstance(claim, CompletenessClaim) or claim not in {
                CompletenessClaim.FINDINGS_ONLY, CompletenessClaim.SCOPED_COMPLETE, CompletenessClaim.PROJECT_COMPLETE}:
            raise _Refusal("unsupported_claim_mode")
        scope, sources, inventory, excluded = _construct_scope(intent, request, current_file)
        if claim == CompletenessClaim.PROJECT_COMPLETE and scope.kind != ScopeKind.PROJECT_PYTHON:
            raise _Refusal("project_claim_requires_project_scope")
        mode = CompletenessClaim.PROJECT_COMPLETE if scope.kind == ScopeKind.PROJECT_PYTHON and claim != CompletenessClaim.FINDINGS_ONLY else claim
        candidate = analyze_scoped_callers(scope, request)
        if candidate.result.coverage.extraction_truncated:
            resources = tuple(d for d in candidate.diagnostics if d.startswith("budget:"))
            raise _Refusal("analysis_truncated:" + ",".join(resources or ("coverage",)))
        if candidate.result.coverage.limitations:
            raise _Refusal("analysis_source_coverage_incomplete")
        if (candidate.source_inventory != inventory or candidate.inventory_exclusions != excluded
                or {f.path: f.digest for f in candidate.fingerprints} != {p: e.digest for p, e in sources.items()}):
            raise _Refusal("sources_or_inventory_changed_after_scope_selection")
        outcome = validate_scoped_callers(candidate, scope, request, claim=mode)
        request.budget.check()  # propagate cancellation even when the validator returns a refusal
        if not outcome.publication_eligible:
            return ScopedCallerAnswerCandidate("refused", "C3 caller answer refused: " + "; ".join(outcome.refusal_reasons) + ".",
                intent, scope, outcome, reasons=outcome.refusal_reasons)
        if outcome.claim != mode:
            raise _Refusal("validator_claim_changed")
        return _render(intent, scope, candidate, outcome, request)
    except OperationCancelled:
        raise
    except _Clarification as exc:
        return ScopedCallerAnswerCandidate("clarification", exc.text, intent, reasons=(exc.reason,), target_options=exc.options)
    except AnalysisBudgetExceeded as exc:
        reason = "analysis_budget_exhausted:" + exc.resource
    except ProjectAccessError:
        reason = "project_authorization_or_containment_changed"
    except _Refusal as exc:
        reason = str(exc)
    except (ValueError, SyntaxError, RecursionError, OSError, TypeError, AttributeError, KeyError):
        reason = "scope_or_evidence_could_not_be_verified"
    # A simultaneous authorization/read failure must not suppress cancellation.
    if isinstance(request, AnalysisRequest):
        try:
            request.budget.check()
        except AnalysisBudgetExceeded:
            pass
    return ScopedCallerAnswerCandidate("refused", "C3 caller answer refused: " + reason + ".",
        intent, scope, reasons=(reason,))
