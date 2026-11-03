"""Internal C2 answer pipeline; no capability, routing, history or voice integration.

Only deterministic factual sentences are rendered. Unpublished previews can
describe uncertainty; the strict CP3 gate remains mandatory for released facts.
Partial-fact publication is deliberately deferred because skipped/unread files
and incomplete inventories cannot yet be revalidated as a complete snapshot.
"""
from models.project_graph import RelationshipGraph, GraphTraversal, PotentialImpact
from models.relationship_answer import RelationshipAnswer
from services.project_relationship_evidence import (
    RelationshipEvidenceError, graph_value, select_relationship_evidence,
    validate_relationship_value, validate_relationship_evidence, organization_payload,
)
from services.project_analysis_freshness import check_graph_publication
from services.project_analysis_request import AnalysisBudgetExceeded
from services.project_access import ProjectAccessError
from services.cancellation import OperationCancelled
from services.source_answer import validate_answer


def render_relationship_evidence(packet, request, order=None):
    """Validated deterministic preview. This function is not a publication gate."""
    validate_relationship_evidence(packet, request)
    propositions = {p.proposition_id: p for p in packet.propositions}
    identities = tuple(propositions) if order is None else tuple(order)
    if len(identities) != len(propositions) or set(identities) != set(propositions):
        raise RelationshipEvidenceError("Organizer changed the approved proposition set.")
    graph = graph_value(packet.value)
    trace = packet.value.traversal if isinstance(packet.value, PotentialImpact) else (
        packet.value if isinstance(packet.value, GraphTraversal) else None)
    complete = trace.complete if trace else graph.analysis.snapshot.coverage.complete and not graph.boundary_ids
    qualification = ("Static source relationships, not observed runtime execution. " if complete else
                     "Incomplete analysis or result: unresolved boundaries or omitted results may remain. "
                     "This is an unpublished preview; no project-wide absence or completeness is claimed. ")
    paragraphs = []
    for index, identity in enumerate(identities):
        request.budget.check()
        proposition = propositions[identity]
        text = (qualification if index == 0 else "") + proposition.text
        paragraphs.append(text + " " + " ".join("[" + source + "]" for source in proposition.source_ids))
    result = validate_answer("\n\n".join(paragraphs), packet)
    if result is None:
        raise RelationshipEvidenceError("Deterministic answer failed strict C1 citation validation.")
    request.check_authorization()
    return result


def answer_relationships(analysis, value, request, *, use_model=False):
    """Release only after current evidence and the unchanged complete-result gate pass.

    Cancellation always propagates, including from the freshness gate. Expected
    evidence/budget failures produce a limitation without leaking tentative facts.
    No model is needed, no rejected prose is returned, and no evidence is persisted.
    """
    snapshot_id = analysis.snapshot.snapshot_id
    def limitation(status, text):
        return RelationshipAnswer(False, text, status, snapshot_id)
    try:
        graph = validate_relationship_value(analysis, value, request)
        trace = value.traversal if isinstance(value, PotentialImpact) else value if isinstance(value, GraphTraversal) else None
        if analysis.snapshot.coverage.cancelled:
            raise OperationCancelled("Analysis was cancelled.")
        if trace is not None and trace.status == "ambiguous":
            return limitation("ambiguous", "The target is ambiguous. Specify a project-relative file and qualified symbol name.")
        complete = trace.complete if trace else analysis.snapshot.coverage.complete and not graph.boundary_ids
        if not complete:
            return limitation("incomplete", "The analysis or result is incomplete, unresolved, or truncated. "
                              "I cannot release relationship facts through the complete-result publication gate. "
                              "Narrow the target or resolve the reported boundaries.")
        packet = select_relationship_evidence(analysis, value, request)
        order = None
        if use_model:
            from services.ai_service import organize_relationship_propositions
            order = organize_relationship_propositions(organization_payload(packet), request)
        text = render_relationship_evidence(packet, request, order)
        freshness = check_graph_publication(value, request)
        if freshness.state == "cancelled":
            raise OperationCancelled("Relationship answer cancelled before publication.")
        if not freshness.verified:
            request.budget.check()
            return limitation(freshness.state, "I could not verify current source, inventory, and authorization. "
                              "No relationship answer was released; please repeat the request.")
        request.check_authorization()
        return RelationshipAnswer(True, text, "success", snapshot_id, order is not None)
    except OperationCancelled:
        raise
    except (RelationshipEvidenceError, AnalysisBudgetExceeded, ProjectAccessError, OSError, ValueError):
        # Check cancellation independently even when another check failed first.
        # budget.check also observes cancellation but a deadline must remain a
        # safe limitation rather than obscuring an already classified failure.
        try:
            request.budget.check()
        except AnalysisBudgetExceeded:
            pass
        return limitation("limitation", "I could not produce a current source-backed answer within the evidence "
                          "and validation limits. Narrow the question or request source excerpts.")
