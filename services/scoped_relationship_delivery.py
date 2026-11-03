"""C3 adapter for the existing multi-file capability and response consumer.

No queue, speaker or persistence lives here. Receipt-bound handles are ephemeral;
the existing router consumes them and the existing speech worker checks playback.
"""
from dataclasses import dataclass, replace
import re

from models.project_scope import CompletenessClaim
from services.cancellation import OperationCancelled, check_cancelled
from services.conversation_service import current_response_delivery
from services.project_analysis_request import AnalysisRequest, AnalysisBudget, AnalysisBudgetExceeded
from services.project_access import ProjectAccessError
from services import scoped_relationship_answer as construction
from services.scoped_relationship_validation import validate_scoped_callers, _final_freshness


@dataclass(frozen=True)
class ScopedPublication:
    answer: object
    request: AnalysisRequest
    receipt: object
    question: str
    scope_id: str
    claim: CompletenessClaim = CompletenessClaim.SCOPED_COMPLETE
    command: str = ""


def _limitation(reasons):
    """Allowlisted user-facing categories; no source expressions or exceptions."""
    value = " ".join(reasons)
    if "project_qualifier" in value:
        return "That named project is not the active authorized project. Select an authorized project explicitly and repeat the question."
    if any(word in value for word in ("authorization", "containment", "project_qualifier")):
        return "I couldn't verify the active project authorization. Select an authorized project and repeat the caller question."
    if any(word in value for word in ("changed", "stale", "fingerprint")):
        return "The source or caller scope changed. I couldn't verify current caller facts. Please repeat the question."
    if any(word in value for word in ("budget", "limit", "truncated", "reservation")):
        return "I couldn't validate the caller answer within the analysis or evidence limits. Specify a smaller explicit scope."
    if any(word in value for word in ("boundar", "coverage", "parse", "support")):
        return "Unresolved calls or incomplete source coverage prevent a complete caller list. Request verified findings only, or specify another scope."
    return "I couldn't independently verify the caller evidence. No caller facts were delivered. Please repeat the question."


def _answer_text(answer):
    if "project_identity_unresolved" in answer.reasons:
        return "That named project is not the active authorized project. Select one registered project explicitly and repeat the question."
    if answer.status == "not_applicable":
        return "Caller chains require a reverse trace. Specify an exact file and qualified symbol."
    return answer.text if answer.status in {"complete", "findings_only", "clarification"} else _limitation(answer.reasons)


def _identity(handle):
    answer = handle.answer
    return (handle.question, handle.command, handle.scope_id, handle.claim, answer.status, answer.text,
            repr(answer.intent), answer.target_options, answer.reasons, id(handle.request), id(handle.request.budget),
            tuple((f.path, f.digest) for f in answer.analysis.fingerprints) if answer.analysis else (),
            answer.scope.scope_id if answer.scope else None,
            answer.validation.claim if answer.validation else None)


def _topic(handle):
    scope = handle.answer.scope
    return {"type": "project", "scoped_relationship": True,
        "project_id": handle.request.context.project_id,
        "authorization_revision": handle.request.context.revision,
        "operation": "calls", "direction": "reverse", "depth": 1,
        "filename": "./" + scope.target.definition.path,
        "qualified_name": scope.target.qualified_name, "scope_id": scope.scope_id,
        "claim": handle.answer.validation.claim.value}


def _pending(handle):
    return {"scoped_relationship": True, "command": handle.command,
            "context": handle.request.context, "claim": handle.claim,
            "candidates": handle.answer.target_options}


def scoped_relationship_capability(*, context, scoped_command, cancellation_event=None,
                                   limits=None, claim=CompletenessClaim.SCOPED_COMPLETE, question=None):
    receipt = current_response_delivery()
    if receipt is None:
        return {"success": False, "error": "A current response receipt is required.", "status": "refused"}
    receipt.guard_publication()
    event = receipt.cancellation_event
    check_cancelled(cancellation_event)
    if cancellation_event is not None and cancellation_event is not event:
        raise OperationCancelled("Cancellation signal does not belong to the response receipt.")
    try:
        request = AnalysisRequest(context, AnalysisBudget(limits, event))
        answer = construction.prepare_scoped_caller_answer(scoped_command, request, claim=claim)
        receipt.check_current()
        factual = answer.status in {"complete", "findings_only"}
        text = _answer_text(answer)
        handle = ScopedPublication(answer, request, receipt, question if question is not None else scoped_command,
                                   answer.scope.scope_id if answer.scope else "", claim, scoped_command)
        receipt.prepare_publication(handle, _identity(handle))
        data = {"success": factual, "status": answer.status, "response": text,
                "_c3_publication": handle}
        if not factual:
            data["error"] = text
        if answer.status == "clarification":
            data["pending"] = {"scoped_relationship": True, "command": scoped_command,
                "context": context, "claim": claim, "candidates": answer.target_options}
        if factual:
            data["topic"] = _topic(handle)
        return data
    except OperationCancelled:
        raise
    except (ProjectAccessError, AnalysisBudgetExceeded, OSError, ValueError):
        receipt.check_current()
        return {"success": False, "status": "refused", "error": _limitation(("authorization_or_budget_limit",))}


def _revalidate(handle):
    handle.receipt.check_current()
    handle.request.check_authorization()
    answer = handle.answer
    if answer.status not in {"complete", "findings_only"}:
        return answer
    if answer.scope.scope_id != handle.scope_id or answer.analysis is None:
        raise ValueError("Scoped publication identity changed.")
    fresh = validate_scoped_callers(answer.analysis, answer.scope, handle.request,
        claim=answer.validation.claim, evidence=answer.validation.evidence)
    handle.request.budget.check()
    if not fresh.publication_eligible:
        return replace(answer, status="refused", text=_limitation(fresh.refusal_reasons),
            relationships=(), references=(), validation=fresh, reasons=fresh.refusal_reasons, analysis=None)
    rendered = construction._render(answer.intent, answer.scope, answer.analysis, fresh, handle.request)
    if (rendered.text, rendered.relationships, rendered.references) != (answer.text, answer.relationships, answer.references):
        raise ValueError("Caller answer or citations changed after validation.")
    handle.receipt.check_current()
    return rendered


def validate_scoped_delivery(result, arguments, cancellation_event=None):
    """Consumer-only, one-use publication gate before text/history/speech."""
    receipt = current_response_delivery()
    if receipt is None:
        raise OperationCancelled("Missing response consumer receipt.")
    receipt.check_current(consumer=True)
    check_cancelled(cancellation_event)
    handle = result.data.get("_c3_publication")
    if handle is None:
        if result.success:
            raise OperationCancelled("Missing C3 factual publication handle.")
        receipt.claim_publication(result)
        result.error = "I couldn't validate a scoped caller response within the active authorization and analysis limits."
        result.data = {"status": "refused", "response": result.error}
        return result
    if (type(handle) is not ScopedPublication or handle.receipt is not receipt
            or handle.question != arguments.get("question")
            or handle.command != arguments.get("scoped_command")
            or handle.request.context != arguments.get("context")
            or receipt.prepared_publication is not handle or receipt.publication_identity != _identity(handle)):
        raise OperationCancelled("Mismatched C3 request/receipt.")
    try:
        answer = _revalidate(handle)
        result.success = answer.status in {"complete", "findings_only"}
        if not result.success:
            text = _answer_text(answer)
            result.error = text
            result.data = {"status": answer.status, "response": text,
                           **({"pending": _pending(handle)} if answer.status == "clarification" else {})}
            if any("project_identity" in r or "project_qualifier" in r for r in answer.reasons):
                result.data = {"status": answer.status, "response": text, "no_history": True}
        else:
            result.data = {"status": answer.status, "response": answer.text,
                           "topic": _topic(handle), "_c3_publication": handle}
        receipt.claim_publication(handle)
        if result.success:
            receipt.playback_guard = lambda: revalidate_scoped_playback(handle)
        return result
    except OperationCancelled:
        raise
    except (ProjectAccessError, AnalysisBudgetExceeded, OSError, ValueError, AttributeError, TypeError) as exc:
        receipt.check_current(consumer=True)
        receipt.claim_publication(handle)
        result.success = False
        reason = ("budget:" + exc.resource if isinstance(exc, AnalysisBudgetExceeded) else
                  "project_authorization_changed" if isinstance(exc, ProjectAccessError) else
                  "source_or_inventory_changed" if isinstance(exc, OSError) else "evidence_invalid")
        result.error = _limitation((reason,))
        result.data = {"status": "refused", "response": result.error}
        return result


def revalidate_scoped_playback(handle):
    """Same request, before each existing speech-worker utterance; no renewal."""
    try:
        handle.receipt.check_publication(handle)
        if handle.receipt.publication_identity != _identity(handle):
            raise ValueError("Playback publication identity changed.")
        from services.capability_state import is_capability_available
        if not is_capability_available("multi_file_reasoning"):
            raise ProjectAccessError("Capability disabled before playback.")
        if handle.answer.scope.scope_id != handle.scope_id:
            raise ValueError("Playback scope identity changed.")
        # Delivery already replayed the complete proof and canonical rendering.
        # Unchanged full dependencies preserve that proof; do not select/charge
        # a new evidence packet for every sentence.
        _final_freshness(handle.answer.analysis, handle.answer.scope, handle.request)
        handle.receipt.check_publication(handle)
        return True
    except (OperationCancelled, ProjectAccessError, AnalysisBudgetExceeded, OSError, ValueError, AttributeError, TypeError):
        pass
    handle.receipt.cancel()
    return False


def resolve_scoped_follow_up(command, pending):
    """Only explicit scope answers or exact displayed target choices; no guesses."""
    if not isinstance(pending, dict) or not pending.get("scoped_relationship"):
        return None
    from services.scoped_relationship_request import parse_scoped_caller_request
    intent = parse_scoped_caller_request(pending["command"])
    text = command.strip().strip("`\"'").rstrip("?!")
    if re.fullmatch(r"(?:within .+|in (?:file|directory|folder) .+|in (?:my|this|our) project)", text, re.I):
        if intent.scope_kind is not None and intent.qualified_name:
            target = (intent.filename + "::" if intent.filename else "") + intent.qualified_name
            return "Show callers of " + target + " " + text
        return pending["command"].rstrip("?!") + " " + text
    selected = [choice for choice in pending["candidates"] if choice.removeprefix("./") == text.removeprefix("./")]
    if len(selected) == 1:
        target = "Show callers of " + selected[0]
        if intent.scope_kind.value == "project_python":
            return target + " in my project"
        return target + " within " + ("file " if intent.scope_kind.value == "files" else "directory ") + intent.scope_path
    return None
