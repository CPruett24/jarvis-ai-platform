"""Explicit INACTIVE planning API. No active router, analyzer or validator calls it.

Exact means a check-time static definition identity, not verified callers, runtime
dispatch, complete support or publication permission. Only qualified targets can
avoid reading the full existing target-lookup domain; no support is eliminated.
"""
import ast
from dataclasses import asdict, dataclass
import json
import os
from types import SimpleNamespace

from models.project_relationships import ProjectIdentity, SourceLocation, SymbolKind
from models.project_scope import SUPPORT_MAX_FILES
from models.source_evidence import RetrievalLimits, RetrievalStatus
from models.target_discovery import TargetIdentityResult, TargetIdentityStatus as Status
from services.cancellation import OperationCancelled
from services.project_access import ProjectAccessError
from services.project_analysis_cache import read_analysis_source
from services.project_analysis_request import AnalysisRequest, AnalysisBudgetExceeded
from services.project_retrieval import discover, permitted
from services.project_symbol_index import extract_scoped_symbols
from services.project_target import resolve_analysis_target
from services.scoped_relationship_request import parse_scoped_caller_request
from services.scoped_relationship_validation import _binding_inventory
from services import scoped_relationship_answer as admission


@dataclass(frozen=True)
class TargetDiscovery:
    result: TargetIdentityResult
    request: AnalysisRequest
    command: str
    current_file: SourceLocation | None = None


class _DiscoveryFailure(ValueError):
    pass


def _stable_definition(target, module):
    lexical = next(scope for scope in module.scopes if scope.symbol == target)
    if target.kind not in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION, SymbolKind.METHOD}:
        return False
    if target.kind != SymbolKind.METHOD and getattr(lexical.node, "decorator_list", ()):
        return False
    if target.qualified_name.split(".")[0] in module.mutations:
        return False
    current = lexical
    while current is not None:
        if current.conditional or current.wildcard:
            return False
        parent = current.parent
        if parent is not None:
            name = current.node.name
            bindings = parent.bindings.get(name, ())
            if name in parent.blocked or len(bindings) != 1 or bindings[0] is not current:
                return False
        current = parent
    return True


def discover_target_identity(command, request, *, current_file=None):
    """Use ONE supplied request/budget; never register projects or renew time.

    The qualified branch verifies its exact physical source before any support
    selection. Unqualified discovery must read every existing lookup candidate;
    exceeding six non-search files refuses rather than guessing or truncating.
    Cancellation propagates. All other limitations return structured metadata.
    """
    if not isinstance(request, AnalysisRequest):
        raise ValueError("A captured AnalysisRequest is required.")
    project = ProjectIdentity(request.context.project_id,
        os.path.normcase(os.path.normpath(str(request.context.root))), request.context.revision)
    intent = parse_scoped_caller_request(command)
    failure_status = Status.REFUSED

    def finish(status, reasons=(), **data):
        result = TargetIdentityResult(project, intent, status, reasons=reasons, **data)
        if status != Status.REFUSED and len(json.dumps(asdict(result), separators=(",", ":")).encode("utf-8")) > request.budget.limits.payload_bytes:
            raise _DiscoveryFailure("target_discovery_payload_limit")
        if status == Status.EXACT:
            request.check_authorization()
        return TargetDiscovery(result, request, command, current_file)

    try:
        request.check_authorization()
        if intent is None or not intent.direct:
            return finish(Status.UNRESOLVED, ("explicit_scoped_direct_target_required",))
        admission._project(intent, request)
        if intent.error:
            return finish(Status.UNRESOLVED, (intent.error,))
        roots, search, inventory, excluded = admission._scope_inventory(intent, request, current_file)
        sources, modules = {}, {}

        def read(path):
            if path in modules:
                return
            request.check_authorization()
            if len(set(sources) - set(search) | ({path} - set(search))) > SUPPORT_MAX_FILES:
                raise _DiscoveryFailure("support_file_limit")
            request.budget.consume(python_files=1)
            result = read_analysis_source(request, path)
            request.budget.check()
            if not result.success or not result.excerpts or result.excerpts[0].truncated:
                if result.limits_reached:
                    raise _DiscoveryFailure("target_source_limit:" + ",".join(result.limits_reached))
                raise _DiscoveryFailure("target_source_unavailable")
            excerpt = result.excerpts[0]
            tree = ast.parse(excerpt.text, filename=path)
            count = 0
            for _ in ast.walk(tree):
                count += 1
                request.budget.consume(ast_nodes=1)
                request.budget.check_file(result.bytes_read, count)
            sources[path] = excerpt
            modules[path] = extract_scoped_symbols(tree, excerpt, request)

        target_path = None
        data = dict(roots=roots, search_files=search, source_inventory=inventory, inventory_exclusions=excluded)
        if intent.filename:
            filename = intent.filename.replace("\\", "/")
            exact = filename.startswith("./") or "/" in filename
            filename = filename.removeprefix("./")
            if not permitted(filename) or ":" in filename or filename.startswith("/"):
                raise _DiscoveryFailure("target_source_denied")
            matches = tuple(path for path in inventory if (path == filename if exact else path.rsplit("/", 1)[-1] == filename))
            if not matches:
                return finish(Status.UNRESOLVED, ("target_file_unresolved",), **data)
            if len(matches) > 32:
                raise _DiscoveryFailure("target_candidate_limit")
            if len(matches) != 1:
                return finish(Status.AMBIGUOUS, ("target_file_ambiguous",), file_options=matches, **data)
            target_path = admission._canonical_path(matches[0], request)
            read(target_path)
            if intent.current_file:
                read(current_file.path)
        else:
            for path in search:
                read(path)
            support = set()
            for module in tuple(modules.values()):
                for observation in module.imports:
                    request.budget.consume(relationships=1)
                    alternatives = _binding_inventory(observation, inventory, excluded)
                    if admission._import_paths(observation, alternatives) - set(inventory):
                        raise _DiscoveryFailure("target_lookup_alternative_unavailable")
                    support.update(admission._import_paths(observation, inventory) - set(search))
                    if len(support) > SUPPORT_MAX_FILES:
                        raise _DiscoveryFailure("support_file_limit")
            for path in sorted(support):
                read(path)
        if intent.current_file and sources[current_file.path].digest != current_file.digest:
            raise _DiscoveryFailure("current_file_context_stale")
        selected = resolve_analysis_target(SimpleNamespace(symbols=tuple(
            scope.symbol for module in modules.values() for scope in module.scopes)),
            filename="./" + target_path if target_path else None, qualified_name=intent.qualified_name)
        # Full dependency rereads detect changes during discovery. They charge
        # actual source bytes; no second parser budget or deadline is created.
        for path, excerpt in sorted(sources.items()):
            fresh = read_analysis_source(request, path)
            request.budget.check()
            if not fresh.success or not fresh.excerpts or fresh.excerpts[0].digest != excerpt.digest:
                raise _DiscoveryFailure("target_sources_changed")
        exclusions = []
        listing = discover(request.context, analysis_request=request, exclusion_diagnostics=exclusions,
            limits=RetrievalLimits(seconds=request.budget.limits.seconds))
        request.check_authorization()
        if (listing.status != RetrievalStatus.SUCCESS or tuple(sorted(path for path in listing.paths if path.lower().endswith(".py"))) != inventory
                or tuple(sorted(exclusions)) != excluded):
            raise _DiscoveryFailure("target_inventory_changed")
        candidates = selected["candidates"]
        if len(candidates) > 32:
            raise _DiscoveryFailure("target_candidate_limit")
        data.update(lookup_files=tuple(sorted(sources)),
            proof_dependencies=tuple(SourceLocation.from_excerpt(project, sources[path]) for path in sorted(sources)),
            candidates=candidates)
        if selected["status"] == "ambiguous":
            return finish(Status.AMBIGUOUS, ("target_identity_ambiguous",), **data)
        if selected["status"] != "resolved":
            return finish(Status.UNRESOLVED, ("target_identity_unresolved",), **data)
        target = selected["target"]
        if not _stable_definition(target, modules[target.definition.path]):
            return finish(Status.UNRESOLVED, ("target_binding_unproven",), **data)
        request.check_authorization()
        return finish(Status.EXACT, target=target, **data)
    except OperationCancelled:
        raise
    except AnalysisBudgetExceeded as exc:
        reason = "target_discovery_budget_exhausted:" + exc.resource
    except ProjectAccessError:
        reason = "target_authorization_or_containment_changed"
    except admission._Clarification as exc:
        reason, failure_status = exc.reason, Status.UNRESOLVED
    except admission._Refusal as exc:
        reason = str(exc)
    except _DiscoveryFailure as exc:
        reason = str(exc)
    except (SyntaxError, RecursionError, OSError, ValueError, TypeError, AttributeError, KeyError):
        reason = "target_source_or_contract_unverifiable"
    try:
        request.budget.check()
    except AnalysisBudgetExceeded as exc:
        reason, failure_status = "target_discovery_budget_exhausted:" + exc.resource, Status.REFUSED
    return finish(failure_status, (reason,))


def revalidate_target_identity(discovery):
    """Before future use, replay under the ORIGINAL request, never a new budget.

    This is not C3.4 caller validation and cannot authorize omission/publication.
    A changed snapshot refuses; it never substitutes a newly discovered target.
    """
    if not isinstance(discovery, TargetDiscovery):
        raise ValueError("An owned target-discovery handle is required.")
    if discovery.result.status != Status.EXACT:
        # A refused/ambiguous result has no usable identity, but must not hide
        # cancellation or silently outlive the original authorization/deadline.
        try:
            discovery.request.check_authorization()
        except AnalysisBudgetExceeded as exc:
            return TargetIdentityResult(discovery.result.project, discovery.result.intent, Status.REFUSED,
                                        reasons=("target_discovery_budget_exhausted:" + exc.resource,))
        except ProjectAccessError:
            return TargetIdentityResult(discovery.result.project, discovery.result.intent, Status.REFUSED,
                                        reasons=("target_authorization_or_containment_changed",))
        return TargetIdentityResult(discovery.result.project, discovery.result.intent, Status.REFUSED,
                                    reasons=("target_identity_not_exact",))
    fresh = discover_target_identity(discovery.command, discovery.request, current_file=discovery.current_file)
    if fresh.result.status == Status.REFUSED:
        return fresh.result
    if fresh.result != discovery.result:
        return TargetIdentityResult(discovery.result.project, discovery.result.intent, Status.REFUSED,
                                    reasons=("target_discovery_changed",))
    return fresh.result
