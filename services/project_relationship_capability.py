"""Read-only C2 capability adapter. Publication belongs to the response consumer."""
import re

from models.project_relationships import RelationshipKind, SymbolKind
from services.cancellation import OperationCancelled, check_cancelled
from services.project_access import ProjectAccessError
from services.project_analysis_request import AnalysisRequest, AnalysisBudget, AnalysisBudgetExceeded
from services.project_analysis_index import analyze_project_relationships
from services.project_graph import build_relationship_graph, traverse_relationships
from services.project_impact import potential_function_impact, potential_file_impact
from services.project_relationship_answer import answer_relationships
from services.project_analysis_freshness import check_graph_publication
from services.project_target import resolve_analysis_target


def limitation(text, status="limitation"):
    return {"success": False, "status": status, "error": text, "response": text}


def relationship_capability(*, context, operation, filename=None, qualified_name=None,
                            direction="forward", depth=2, comparison=None, question="",
                            cancellation_event=None, limits=None, use_model=False,
                            scoped_command=None, claim=None):
    """One captured authorization, one budget, canonical CP2-4 analysis only.

    No history, speech, topic state, model target resolution, or root registration.
    The private publication handle is consumed locally and never persisted.
    """
    if scoped_command is not None:
        from services.scoped_relationship_delivery import scoped_relationship_capability
        from models.project_scope import CompletenessClaim
        return scoped_relationship_capability(context=context, scoped_command=scoped_command,
            cancellation_event=cancellation_event, limits=limits, question=question,
            claim=CompletenessClaim.SCOPED_COMPLETE if claim is None else claim)
    check_cancelled(cancellation_event)
    try:
        request = AnalysisRequest(context, AnalysisBudget(limits, cancellation_event))
        request.check_authorization()
        request.budget.check_depth(depth)
        if operation not in {"calls", "imports", "trace", "impact", "connections"}:
            return limitation("Unsupported relationship operation.")
        if direction not in {"forward", "reverse"} or depth < 1:
            return limitation("Specify a forward or reverse direction and a positive bounded depth.")
        analysis = analyze_project_relationships(request)
        selected = resolve_analysis_target(analysis, filename, qualified_name)
        request.check_authorization()
        base = {"operation": operation, "filename": filename, "qualified_name": qualified_name,
                "direction": direction, "depth": depth, "comparison": comparison}
        if selected["status"] == "ambiguous":
            candidates = sorted({"./" + s.definition.path + ("::" + s.qualified_name if s.kind != SymbolKind.MODULE else "")
                                 for s in selected["candidates"]})
            return {**limitation("The target is ambiguous. Specify one qualified identity:\n" +
                                "\n".join(candidates), "ambiguous"), "candidates": candidates,
                    "pending": {**base, "relationship_grounded": True,
                                "project_id": context.project_id, "authorization_revision": context.revision,
                                "candidates": candidates}}
        if selected["status"] != "resolved":
            return limitation("I could not find that exact target in the analyzed authorized Python sources. "
                              "This does not establish its absence from unread or dynamic code.", "not_found")
        target = selected["target"]
        base.update(filename="./" + target.definition.path,
                    qualified_name=qualified_name if qualified_name is not None else None)
        if operation == "connections":
            # CP3 has no two-endpoint path result whose closure CP4 can validate.
            return limitation("I cannot safely publish a two-target connection with the current trace contract. "
                              "Request a forward trace or reverse callers instead. This does not establish "
                              "that no runtime connection exists.")
        kind = RelationshipKind.IMPORTS if operation == "imports" else RelationshipKind.CALLS
        if operation == "impact":
            value = (potential_function_impact(analysis, request, filename=base["filename"],
                     qualified_name=qualified_name, max_depth=depth) if qualified_name is not None else
                     potential_file_impact(analysis, request, base["filename"], kind=kind, max_depth=depth))
        else:
            graph = build_relationship_graph(analysis, request, kind)
            value = traverse_relationships(graph, request, filename=base["filename"],
                qualified_name=qualified_name, direction=direction, max_depth=depth)
        answer = answer_relationships(analysis, value, request, use_model=use_model)
        if not answer.success:
            return limitation(answer.text, answer.status)
        topic = {**base, "type": "project", "relationship_grounded": True,
                 "project_id": context.project_id, "authorization_revision": context.revision,
                 "target_identity": target.symbol_id}
        return {"success": True, "response": answer.text, "status": answer.status,
                "topic": topic, "observations": {"project": context.project_id,
                    "snapshot": answer.snapshot_id, "source_backed_answer": answer.text},
                "_publication": (value, request)}
    except OperationCancelled:
        raise
    except (ProjectAccessError, AnalysisBudgetExceeded, OSError, ValueError):
        check_cancelled(cancellation_event)
        return limitation("I could not verify a complete current relationship analysis within the authorized "
                          "source and budget limits. Narrow the question or repeat it in the active project.")


def validate_relationship_delivery(result, cancellation_event=None):
    """Recheck queued results at the existing response consumer, using the SAME budget."""
    check_cancelled(cancellation_event)
    if result.success:
        try:
            value, request = result.data["_publication"]
            freshness = check_graph_publication(value, request)
            check_cancelled(cancellation_event)
            if freshness.state == "cancelled":
                raise OperationCancelled("Relationship publication cancelled.")
            if not freshness.verified:
                raise ProjectAccessError("Queued sources changed.")
            request.check_authorization()
        except (ProjectAccessError, AnalysisBudgetExceeded, OSError, ValueError, KeyError):
            result.success = False
            result.error = "I could not verify current sources and authorization before delivery. Please repeat the question."
            result.data = {}
    return result


def relationship_speech(text):
    """Only citation metadata is removed; factual qualifications remain verbatim."""
    return re.sub(r"[ \t]+", " ", re.sub(r"\[[^\]\n]+\]", "", text)).strip()
