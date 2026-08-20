from pathlib import Path
import re

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "venv",
    ".idea",
    ".vscode",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
}

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
    return Path(__file__).resolve().parent.parent


def _is_project_file(path: Path) -> bool:
    """Returns True if the path is a source file that belongs to the project."""

    if any(part in EXCLUDED_DIRECTORIES for part in path.parts):
        return False

    if not path.is_file():
        return False

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False

    return True


def _project_files():
    """Returns all searchable project files."""

    root = _project_root()

    return [
        path
        for path in root.rglob("*")
        if _is_project_file(path)
    ]


def _find_matching_files(filename):

    query = filename.lower().strip()

    if query.endswith(".py"):
        query = query[:-3]

    query = (
        query
        .replace("_", "")
        .replace(" ", "")
    )

    matches = []

    for path in _project_files():

        stem = (
            path.stem.lower()
            .replace("_", "")
            .replace(" ", "")
        )

        if query == stem:
            matches.insert(0, path)

        elif query in stem:
            matches.append(path)

    return matches

def find_matching_files(filename):

    return _find_matching_files(filename)

def summarize_file(filename):

    matches = _find_matching_files(filename)

    if not matches:
        return None

    file = matches[0]

    try:
        content = file.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception:
        return None

    lines = len(content.splitlines())

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

    search_terms = {
        keyword.lower(),
        keyword.lower().replace(" ", "_"),
    }

    results = []

    for path in _project_files():

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        except Exception:
            continue

        content_lower = content.lower()

        if any(term in content_lower for term in search_terms):
            results.append(path)

    return results

def get_file_content(filename, max_lines=300):

    matches = _find_matching_files(filename)

    if not matches:
        return None

    file = matches[0]

    try:

        content = file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except Exception:
        return None

    lines = content.splitlines()

    truncated = False

    if len(lines) > max_lines:

        lines = lines[:max_lines]

        truncated = True

    return {
        "path": file,
        "filename": file.name,
        "content": "\n".join(lines),
        "line_count": len(content.splitlines()),
        "truncated": truncated,
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