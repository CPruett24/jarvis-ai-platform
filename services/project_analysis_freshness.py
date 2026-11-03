"""Explicit C2 publication gate; retained snapshots never imply current source.

Freshness is verified at check time, not an atomic filesystem transaction. The
same request budget pays for both inventory passes and all fingerprint re-reads.
There is no new deadline, unsafe fallback, or implicit authorization.
"""
from dataclasses import replace

from models.project_graph import FreshnessCheck, GraphTraversal, PotentialImpact, RelationshipGraph
from models.source_evidence import RetrievalLimits, RetrievalStatus
from services.cancellation import OperationCancelled
from services.project_access import ProjectAccessError
from services.project_analysis_request import AnalysisBudgetExceeded
from services.project_graph import _validate_analysis_owner
from services import project_retrieval
from services.project_analysis_cache import read_analysis_source


def check_snapshot_freshness(analysis, request):
    """Fail closed on incomplete coverage, changed inventory/source or failed checks.

    All discovered permitted files and policy-excluded entries must still match.
    Unsupported/unparsed coverage cannot justify project-wide absence claims.
    """
    snapshot = analysis.snapshot
    identity = snapshot.snapshot_id
    def result(state, reason):
        return FreshnessCheck(identity, state, (reason,))
    def inventory():
        exclusions = []
        listing = project_retrieval.discover(request.context, analysis_request=request,
            exclusion_diagnostics=exclusions,
            limits=replace(RetrievalLimits(), seconds=request.budget.limits.seconds))
        if listing.status == RetrievalStatus.CANCELLED:
            raise OperationCancelled()
        if listing.status != RetrievalStatus.SUCCESS:
            return result("unverified", "freshness_inventory_incomplete:" + ",".join(listing.limits_reached))
        paths = tuple(sorted(listing.paths + [path for path, _ in exclusions]))
        expected_exclusions = {(d.path, d.reason) for d in snapshot.coverage.excluded}
        if paths != tuple(sorted(snapshot.coverage.discovered)) or set(exclusions) != expected_exclusions:
            return result("stale", "source_inventory_changed")
        return None
    try:
        _validate_analysis_owner(analysis, request)
        if not snapshot.coverage.complete:
            return result("unverified", "analysis_coverage_incomplete")
        failure = inventory()
        if failure:
            return failure
        for fingerprint in snapshot.fingerprints:
            request.check_authorization()
            fresh = read_analysis_source(request, fingerprint.path)
            if fresh.status == RetrievalStatus.CANCELLED:
                raise OperationCancelled()
            if not fresh.success or not fresh.excerpts or fresh.excerpts[0].truncated:
                resources = [r.removeprefix("analysis:") for r in fresh.limits_reached if r.startswith("analysis:")]
                if resources:
                    return result("unverified", "freshness_budget_exhausted:" + ",".join(resources))
                return result("unverified", "source_fingerprint_unavailable:" + fingerprint.path)
            if fresh.excerpts[0].digest != fingerprint.digest:
                return result("stale", "source_digest_changed:" + fingerprint.path)
        failure = inventory()  # Catch additions/deletions during the read pass too.
        if failure:
            return failure
        _validate_analysis_owner(analysis, request)
        return FreshnessCheck(identity, "verified")
    except ProjectAccessError:
        return result("stale", "project_authorization_changed")
    except AnalysisBudgetExceeded as exc:
        return result("unverified", "freshness_budget_exhausted:" + exc.resource)
    except OperationCancelled:
        return result("cancelled", "freshness_cancelled")
    except OSError:
        return result("unverified", "freshness_filesystem_check_failed")


def check_graph_publication(value, request):
    """Mandatory future delivery gate; no live presentation is introduced here.

    Incomplete traversals/impact and uncertain boundaries cannot be promoted into
    complete/absence claims. This conservative gate currently refuses them.
    """
    if isinstance(value, PotentialImpact):
        value = value.traversal
    if isinstance(value, GraphTraversal):
        graph, complete = value.graph, value.complete
    elif isinstance(value, RelationshipGraph):
        graph = value
        complete = graph.analysis.snapshot.coverage.complete and not graph.boundary_ids
    else:
        raise ValueError("Expected a canonical C2 graph, traversal or potential impact result.")
    try:
        _validate_analysis_owner(graph.analysis, request)
    except ProjectAccessError:
        return FreshnessCheck(graph.snapshot_id, "stale", ("project_authorization_changed",))
    except AnalysisBudgetExceeded as exc:
        return FreshnessCheck(graph.snapshot_id, "unverified", ("freshness_budget_exhausted:" + exc.resource,))
    except OperationCancelled:
        return FreshnessCheck(graph.snapshot_id, "cancelled", ("freshness_cancelled",))
    except OSError:
        return FreshnessCheck(graph.snapshot_id, "unverified", ("freshness_filesystem_check_failed",))
    if not complete:
        return FreshnessCheck(graph.snapshot_id, "unverified", ("graph_or_traversal_incomplete",))
    return check_snapshot_freshness(graph.analysis, request)
