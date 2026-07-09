from pathlib import Path
import re

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
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


def _project_root():
    return Path.cwd()


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