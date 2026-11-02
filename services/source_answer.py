"""Evidence validation and presentation shared by local project capabilities."""
from dataclasses import asdict, replace
import re
import html
import unicodedata
from urllib.parse import unquote

from models.source_evidence import RetrievalLimits, RetrievalStatus
from services.project_access import get_project
from services.project_retrieval import discover, read_source
from services.project_service import retrieve_project_sources
from services.cancellation import check_cancelled


def evidence_is_current(result, cancellation_event=None):
    try:
        context = get_project(result.project_id)
        if context != get_project() or context.revision != result.revision:
            return False
        for excerpt in result.excerpts:
            check_cancelled(cancellation_event)
            fresh = read_source(excerpt.path, context, start_line=excerpt.start_line,
                                cancellation_event=cancellation_event)
            if not fresh.success or not fresh.excerpts or fresh.excerpts[0].digest != excerpt.digest:
                return False
        return True
    except (ValueError, OSError):
        return False


# Source IDs are preferred. Explicit references are accepted only when a single
# retrieved excerpt covers the requested relative path and inclusive line range.
# Recognize unknown extensions too: they must not be an escape from validation.
_SOURCE_PATH = r"(?P<path>[\w./\\~+-]*\.[^\W\d_]\w*)"
_SOURCE_REFERENCE = re.compile(
    _SOURCE_PATH + r"\s*(?:(?::|#)\s*(?:lines?\s*)?L?|(?:[, (]+\s*)?(?:(?:at|on)\s+)?lines?\s+)"
    r"(?P<start>\d+)(?:\s*(?:-|to|through)\s*L?(?P<end>\d+))?"
    r"(?=$|[\s\].,;!?)}])", re.I,
)
_SOURCE_MENTION = re.compile(_SOURCE_PATH, re.I)


def _reference_text(text):
    """Canonical audit view: encoded/Unicode/Markdown variants cannot hide refs."""
    for _ in range(5):
        decoded = html.unescape(unquote(text))
        if decoded == text:
            break
        text = decoded
    if re.search(r"%[0-9a-f]{2}|&(?:#\w+|\w+);", text, re.I):
        raise ValueError("Ambiguous encoded reference")
    text = unicodedata.normalize("NFKC", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = text.translate(str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2011": "-", "\u2044": "/", "\u2216": "\\"}))
    text = text.replace("`", "").replace("*", "")
    text = re.sub(r"\s*([/\\])\s*", r"\1", text)
    return re.sub(r"(?<=\w)\s*\.\s*(?=\w)", ".", text)


def _covered_reference(match, excerpts):
    path = match["path"].replace("\\", "/")
    if path.startswith("/") or ".." in path.split("/"):
        return None
    start, end = int(match["start"]), int(match["end"] or match["start"])
    if start < 1 or end < start:
        return None
    candidates = [excerpt for excerpt in excerpts
                  if excerpt.path.replace("\\", "/").casefold() == path.casefold()
                  and excerpt.start_line <= start <= end <= excerpt.end_line]
    if not candidates:
        return None
    return f"{candidates[0].path}:{start}\u2013{end}"


def validate_answer(answer, result):
    """Validate references, not the semantic truth of a model interpretation."""
    if not isinstance(answer, str) or not answer.strip() or "\x00" in answer:
        return None
    sources = {excerpt.source_id: excerpt for excerpt in result.excerpts}
    rendered = []
    try:
        # Decode before processing brackets so encoded bracket citations are
        # checked as citations too. Rendering always uses retrieval records.
        text = answer
        for _ in range(5):
            decoded = html.unescape(unquote(text))
            if decoded == text:
                break
            text = decoded
        _reference_text(text)  # rejects ambiguous residual encoding

        def citation(match):
            token = match[1].strip()
            if token in sources:
                excerpt = sources[token]
                reference = f"{excerpt.path}:{excerpt.start_line}\u2013{excerpt.end_line}"
            else:
                direct = _SOURCE_REFERENCE.fullmatch(_reference_text(token))
                reference = _covered_reference(direct, result.excerpts) if direct else None
                if reference is None:
                    raise ValueError("Unsupported source reference")
            rendered.append("[" + reference + "]")
            return f"\x00C{len(rendered) - 1}\x00"

        text = re.sub(r"\[([^\]\n]+)\]", citation, text)
        view = _reference_text(text)
        refs = {match.start(): match for match in _SOURCE_REFERENCE.finditer(view)}
        for match in refs.values():
            if _covered_reference(match, result.excerpts) is None:
                return None
        for mention in _SOURCE_MENTION.finditer(view):
            tail = view[mention.end():]
            if mention.start() and view[mention.start() - 1] == ":":
                return None  # A drive/scheme prefix is not a project-relative path.
            before = re.search(r"\blines?\s+(?P<start>\d+)(?:\s*(?:-|to|through)\s*(?P<end>\d+))?\s+(?:of|in|from)\s*$",
                               view[:mention.start()], re.I)
            if before and _covered_reference({"path": mention["path"], "start": before["start"],
                                              "end": before["end"]}, result.excerpts) is None:
                return None
            # Unsupported reference syntax is denied, not silently interpreted
            # as a harmless filename mention beside a valid source ID.
            suspicious = (re.match(r"\s*[:#]", tail) or
                re.match(r"\s*(?:(?:at|on)\s+)?lines?(?=\s|[=:]|\d)", tail, re.I) or
                re.match(r"\s*(?:[^\w\s]|\s|at\b|on\b|lines?(?=\s|[=:]|\d)|L(?=\d))*\d", tail, re.I))
            if suspicious and mention.start() not in refs:
                return None
        paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
        for paragraph in paragraphs:
            if "\x00C" not in paragraph and not _SOURCE_REFERENCE.search(_reference_text(paragraph)):
                return None
        if not rendered and not refs:
            return None
        for index, reference in enumerate(rendered):
            text = text.replace(f"\x00C{index}\x00", reference)
        return text.strip()
    except (ValueError, OverflowError):
        return None


def source_capability(question="", filename=None, operation="read", recursive=False,
                      project_id=None, authorization_revision=None, cancellation_event=None, detail_depth=1,
                      selection_id=None):
    context = get_project(project_id)
    from services.capability_state import is_capability_available
    required = {"summary": "file_summary", "list": "project_tree", "read": "code_explanation",
                "search": "project_search", "excerpt": "code_explanation",
                "projects": "project_source", "select": "project_source"}.get(operation)
    if required is None:
        return {"success": False, "error": "Unsupported source operation.", "status": "unsupported"}
    if not is_capability_available(required):
        return {"success": False, "error": f"The {required} capability is disabled or unavailable.", "status": "denied"}
    if operation == "projects":
        from services.project_access import list_projects
        ids = [project.project_id for project in list_projects()]
        return {"success": True, "status": "success", "response": "Authorized projects: " + ", ".join(ids),
                "observations": {"authorized_projects": ids}}
    if operation == "select":
        from services.project_access import select_project, ProjectAccessError
        try:
            context = select_project(selection_id)
        except ProjectAccessError as exc:
            return {"success": False, "status": "denied", "error": str(exc)}
        return {"success": True, "status": "success", "response": f"Selected authorized project {context.project_id}.",
                "observations": {"active_project": context.project_id, "authorization_revision": context.revision}}
    if context != get_project() or (authorization_revision is not None and
                                  context.revision != authorization_revision):
        return {"success": False, "error": "Project authorization changed; please repeat the request.",
                "status": "stale"}
    if operation in {"read", "summary", "excerpt"} and not filename:
        return {"success": False, "status": "ambiguous", "needs_filename": True,
                "error": "Which project file would you like me to read?", "candidates": []}
    check_cancelled(cancellation_event)
    if operation == "list":
        result = discover(context, recursive=recursive, cancellation_event=cancellation_event)
    else:
        limits = RetrievalLimits()
        if operation == "summary":
            limits = replace(limits, max_lines=1000000)
        result = retrieve_project_sources(filename or question, context=context,
            search=operation == "search", limits=limits, cancellation_event=cancellation_event)
    data = {"success": result.success, "status": result.status.value,
            "retrieval": asdict(result), "observations": {}}
    if context != get_project():
        return {**data, "success": False, "error": "Active project changed during retrieval.", "status": "stale"}
    if not result.success:
        data["error"] = result.error or f"Source retrieval: {result.status.value}."
        if result.candidates:
            data["error"] = "Multiple files match. Specify a project-relative path: " + ", ".join(result.candidates)
            # Router owns clarification, speech, and history.
            data["candidates"] = result.candidates
        return data
    if operation == "list":
        scope = "recursive" if recursive else "top-level"
        data["response"] = f"Readable {scope} entries in {context.project_id}:\n" + "\n".join(result.paths)
        if result.limits_reached:
            data["response"] += "\nPartial inventory; traversal limits were reached."
        data["observations"] = {"project_id": context.project_id, "paths": result.paths,
                                "scope": scope, "limits": result.limits_reached}
        return data
    if not result.excerpts:
        return {**data, "success": False, "error": "No source excerpts were retrieved."}
    if operation == "summary":
        excerpt = result.excerpts[0]
        if excerpt.truncated:
            return {**data, "success": False, "error": "File exceeds summary evidence limits; whole-file counts are unavailable."}
        text = excerpt.text
        data["response"] = (f"{excerpt.path} contains {excerpt.total_lines} lines, "
            f"{len(re.findall(r'^def\s', text, re.M))} functions, and "
            f"{len(re.findall(r'^class\s', text, re.M))} classes. "
            f"[{excerpt.path}:{excerpt.start_line}–{excerpt.end_line}]")
    elif operation == "excerpt":
        excerpt = result.excerpts[0]
        numbered = "\n".join(f"{excerpt.start_line + offset}: {line}"
                             for offset, line in enumerate(excerpt.text.split("\n")))
        data["response"] = (f"Observed source [{excerpt.path}:{excerpt.start_line}–{excerpt.end_line}]:\n" + numbered)
        if excerpt.truncated:
            data["response"] += "\nPartial excerpt; omitted lines were not included."
    else:
        from services.ai_service import generate_source_answer
        try:
            raw = generate_source_answer((question or f"Explain {filename}") + f" Detail level: {detail_depth}.", result,
                                         cancellation_event=cancellation_event)
        except Exception as exc:
            from services.cancellation import OperationCancelled
            if isinstance(exc, OperationCancelled):
                raise
            return {**data, "success": False, "error": "Source answer generation failed."}
        check_cancelled(cancellation_event)
        response = validate_answer(raw, result)
        if response is None:
            return {**data, "success": False, "error": "I retrieved source excerpts, but could not produce an answer with valid source references after one regeneration. Please narrow the question or request a source excerpt."}
        data["response"] = "Interpretation of retrieved source:\n" + response
        if result.status == RetrievalStatus.PARTIAL or any(e.truncated for e in result.excerpts):
            data["response"] += "\nEvidence is partial; this answer covers only the retrieved excerpts."
    if not evidence_is_current(result, cancellation_event):
        return {**data, "success": False, "status": "stale",
                "error": "Source or authorization changed while answering; please retry."}
    data["observations"] = {"project_id": context.project_id, "sources": [
        {"path": e.path, "start_line": e.start_line, "end_line": e.end_line,
         "digest": e.digest, "truncated": e.truncated} for e in result.excerpts]}
    data["topic"] = {"type": "file" if len(result.excerpts) == 1 else "project",
                     "project_id": context.project_id, "authorization_revision": context.revision,
                     "filename": result.excerpts[0].path, "source_grounded": True, "depth": detail_depth}
    return data


def summarize_source_capability(filename=None):
    return source_capability(filename=filename, operation="summary")


def explain_source_capability(filename=None, depth=1):
    result = source_capability(filename=filename,
                              question=f"Explain {filename} at detail level {depth}.")
    if result.get("topic"):
        result["topic"]["depth"] = depth
    return result
