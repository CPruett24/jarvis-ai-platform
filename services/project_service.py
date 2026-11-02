from pathlib import Path
import re
from dataclasses import replace
from services.project_access import get_project, resolve_project_path, ProjectAccessError
from services.project_retrieval import (discover, read_source, permitted,
                                        EXCLUDED_DIRECTORIES, SUPPORTED_EXTENSIONS)
from models.source_evidence import RetrievalLimits, RetrievalResult, RetrievalStatus
from services.project_retrieval import Budget, BudgetExceeded
from services.cancellation import OperationCancelled
import time

FILE_CATEGORIES = {
    "test": {
        "directories": {"tests", "test"},
        "filename_prefixes": ("test_",),
    },
    "documentation": {
        "directories": {"docs"},
        "extensions": {".md", ".txt"},
    },
    "configuration": {
        "extensions": {
            ".json",
            ".yaml",
            ".yml",
        },
    },
}

def classify_project_file(path: Path):
    """
    Classify a project file by its architectural role.
    """

    relative_path = path.relative_to(
        _project_root()
    )

    parts = relative_path.parts

    if parts:

        top_level = parts[0].lower()

        if top_level in FILE_CATEGORIES["test"]["directories"]:
            return "test"

        if top_level in FILE_CATEGORIES["documentation"]["directories"]:
            return "documentation"

    filename = path.name.lower()

    if filename.startswith(
        FILE_CATEGORIES["test"]["filename_prefixes"]
    ):
        return "test"

    if path.suffix.lower() in FILE_CATEGORIES["documentation"]["extensions"]:
        return "documentation"

    if path.suffix.lower() in FILE_CATEGORIES["configuration"]["extensions"]:
        return "configuration"

    return "application"


def _project_root():
    return get_project().root


def _is_project_file(path: Path) -> bool:
    """Returns True if the path is a source file that belongs to the project."""

    try:
        context = get_project()
        relative = path.relative_to(context.root)
        resolved = resolve_project_path(context, relative)
        return permitted(relative) and resolved.is_file()
    except (ValueError, OSError, ProjectAccessError):
        return False


def _project_files():
    """Returns all searchable project files."""

    from services.project_access import require_legacy_project
    context = require_legacy_project()
    result = discover(context)
    return [context.root / path for path in result.paths] if result.success else []


def _find_matching_files(filename):

    query = filename.lower().strip()

    if "/" in query or "\\" in query:
        try:
            target = resolve_project_path(get_project(), filename)
        except (ProjectAccessError, OSError):
            return []
        return [target] if _is_project_file(target) else []

    if query.endswith(".py"):
        query = query[:-3]

    query = (
        query
        .replace("_", "")
        .replace(" ", "")
    )

    matches = []
    exact = []

    for path in _project_files():

        stem = (
            path.stem.lower()
            .replace("_", "")
            .replace(" ", "")
        )

        if query == stem:
            exact.append(path)

        elif query in stem:
            matches.append(path)

    return sorted(exact or matches, key=lambda path: path.as_posix().casefold())

def find_matching_files(filename):
    from services.project_access import require_legacy_project
    require_legacy_project()
    return _find_matching_files(filename)

def summarize_file(filename):

    matches = _find_matching_files(filename)

    if len(matches) != 1:
        return None

    file = matches[0]

    try:
        result = read_source(file.relative_to(_project_root()).as_posix(),
            limits=replace(RetrievalLimits(), max_lines=1000000, max_evidence_bytes=512 * 1024))
        if not result.success or not result.excerpts or result.excerpts[0].truncated:
            return None
        content = result.excerpts[0].text

    except Exception:
        return None

    lines = result.excerpts[0].total_lines

    imports = len(
        re.findall(
            r"^(import|from)\s",
            content,
            re.MULTILINE,
        )
    )

    functions = len(
        re.findall(
            r"^def\s",
            content,
            re.MULTILINE,
        )
    )

    classes = len(
        re.findall(
            r"^class\s",
            content,
            re.MULTILINE,
        )
    )

    return {
        "path": file,
        "lines": lines,
        "imports": imports,
        "functions": functions,
        "classes": classes,
    }


def search_project(keyword):
    result = retrieve_project_sources(keyword, search=True)
    return [_project_root() / path for path in result.paths]


def retrieve_project_sources(target, *, search=False, context=None, limits=None,
                             cancellation_event=None):
    """Resolve/read one file or retrieve ranked excerpts for a project question."""
    context = context or get_project()
    limits = limits or RetrievalLimits()
    budget = Budget(limits, cancellation_event)
    result = RetrievalResult(context.project_id, context.revision, "search" if search else "read",
                             RetrievalStatus.NOT_FOUND)
    try:
        budget.check()
        normalized = target.strip().strip('"\'').replace("\\", "/")
        if not search and ("/" in normalized or ":" in normalized or normalized.startswith(".")):
            return read_source(normalized, context, limits=limits, cancellation_event=cancellation_event)
        listing = discover(context, limits=limits, cancellation_event=cancellation_event)
        result.entries_visited = listing.entries_visited
        result.limits_reached.extend(listing.limits_reached)
        if not listing.success:
            return listing
        if not search and listing.status == RetrievalStatus.PARTIAL:
            result.status = RetrievalStatus.BUDGET_EXCEEDED
            result.error = "Discovery was incomplete; specify an exact project-relative path."
            return result
        query = normalized.casefold()
        if not search:
            exact = [path for path in listing.paths if Path(path).name.casefold() == query]
            stem = [path for path in listing.paths if _normalize_identifier(Path(path).stem) ==
                    _normalize_identifier(Path(query).stem)]
            matches = exact or stem
            if len(matches) > 1:
                result.status, result.candidates = RetrievalStatus.AMBIGUOUS, matches
                return result
            if matches:
                return read_source(matches[0], context, limits=replace(limits,
                    seconds=max(0.001, budget.deadline - time.monotonic())), cancellation_event=cancellation_event)
            result.error = "No matching readable file."
            return result
        tokens = {token for token in re.findall(r"[a-z][a-z0-9_]+", query)
                  if token not in {"explain", "project", "this", "the", "does", "what", "how",
                                   "handles", "handle", "about", "please", "with", "and", "for"}}
        ranked = []
        for path in sorted(listing.paths, key=lambda path: (
                -sum(token in path.casefold() for token in tokens),
                path.startswith(("tests/", "test/", "docs/")), path.casefold())):
            if len(ranked) >= limits.max_excerpts:
                result.limits_reached.append("candidate_limit")
                break
            budget.check()
            remaining = limits.max_search_bytes - budget.bytes
            if remaining <= 0:
                raise BudgetExceeded("search_bytes")
            read = read_source(path, context, limits=replace(limits,
                max_file_bytes=min(limits.max_file_bytes, remaining), max_lines=1000000,
                max_evidence_bytes=limits.max_file_bytes,
                seconds=max(0.001, budget.deadline - time.monotonic())), cancellation_event=cancellation_event)
            budget.bytes += read.bytes_read
            if read.status == RetrievalStatus.CANCELLED:
                raise OperationCancelled()
            if not read.success or not read.excerpts:
                result.limits_reached.append(f"unreadable:{path}:{read.status.value}")
                continue
            full = read.excerpts[0]
            lines = full.text.split("\n")
            hits = [index for index, line in enumerate(lines) if any(token in line.casefold() for token in tokens)]
            score = sum(token in path.casefold() for token in tokens) * 10 + min(len(hits), 10)
            if score:
                start = max(0, (hits[0] if hits else 0) - 10)
                selected, used = [], 0
                for line in lines[start:start + limits.max_lines]:
                    cost = len(line.encode("utf-8")) + 1
                    if used + cost > limits.max_evidence_bytes:
                        break
                    selected.append(line)
                    used += cost
                if selected:
                    ranked.append((score, replace(full, start_line=start + 1,
                        end_line=start + len(selected), text="\n".join(selected),
                        truncated=start > 0 or start + len(selected) < len(lines))))
        total = 0
        for _, excerpt in sorted(ranked, key=lambda item: (-item[0], item[1].path)):
            cost = len(excerpt.text.encode("utf-8"))
            if len(result.excerpts) >= limits.max_excerpts or total + cost > limits.max_evidence_bytes:
                result.limits_reached.append("evidence_budget")
                break
            result.excerpts.append(excerpt)
            result.paths.append(excerpt.path)
            total += cost
        if result.excerpts:
            result.status = RetrievalStatus.PARTIAL if result.limits_reached or any(
                excerpt.truncated for excerpt in result.excerpts) else RetrievalStatus.SUCCESS
        else:
            result.error = "No relevant readable source evidence was found."
    except BudgetExceeded as exc:
        result.status = RetrievalStatus.BUDGET_EXCEEDED
        result.limits_reached.append(str(exc))
    except OperationCancelled:
        result.status = RetrievalStatus.CANCELLED
    except (ProjectAccessError, OSError) as exc:
        result.status, result.error = RetrievalStatus.DENIED, str(exc)
    result.bytes_read = budget.bytes
    return result

def get_file_content(filename, max_lines=300):
    """Compatibility wrapper over the same authorized reader used by C1."""
    result = retrieve_project_sources(filename, limits=replace(RetrievalLimits(), max_lines=max_lines))
    if not result.success or not result.excerpts:
        return None
    excerpt = result.excerpts[0]
    file = _project_root() / excerpt.path
    return {
        "path": file, "filename": file.name, "content": excerpt.text,
        "line_count": excerpt.total_lines, "truncated": excerpt.truncated, "evidence": result,
    }


def get_project_state():
    """
    Return a structured snapshot of the current project.

    This represents the actual files that currently exist,
    rather than the files described in project documentation.
    """

    root = _project_root()

    files = _project_files()

    state = {
        "project_name": root.name,
        "project_root": str(root),
        "file_count": len(files),
        "directories": {},
    }

    for path in sorted(files):

        relative_path = path.relative_to(root)

        parts = relative_path.parts

        if len(parts) == 1:
            directory = "root"
        else:
            directory = parts[0]

        state["directories"].setdefault(
            directory,
            [],
        )

        state["directories"][directory].append(
            str(relative_path)
        )

    return state

def format_project_state(state):
    """
    Convert project state into concise text suitable for AI context.
    """

    lines = [
        f"Project: {state['project_name']}",
        f"File count: {state['file_count']}",
        "",
        "Project files:",
    ]

    for directory, files in state["directories"].items():

        lines.append(
            f"\n[{directory}]"
        )

        for file in files:

            normalized_file = file.replace(
                "\\",
                "/",
            )

            lines.append(
                f"- {normalized_file}"
            )

    return "\n".join(lines)

def _normalize_identifier(text):
    """
    Normalize identifiers for comparison.
    """

    text = text.lower()

    return (
        text
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )
