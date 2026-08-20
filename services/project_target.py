from pathlib import Path

from services.project_analysis_index import (
    get_project_analysis_index,
)

from services.project_service import (
    _normalize_identifier,
)

import re

TARGET_PATTERNS = [
    r"\bif i change\s+(.+?)(?:\?|$)",
    r"\bif i modify\s+(.+?)(?:\?|$)",
    r"\bchanging\s+(.+?)(?:\?|$)",
    r"\bmodify\s+(.+?)(?:\?|$)",
    r"\bchange\s+(.+?)(?:\?|$)",
    r"\bwhat depends on\s+(.+?)(?:\?|$)",
    r"\bwhat uses\s+(.+?)(?:\?|$)",
    r"\bwho calls\s+(.+?)(?:\?|$)",
]


def extract_target_candidate(command):
    """
    Extract the likely project target from an
    impact-analysis question.

    Returns the raw candidate string or None.
    """

    import re

    command = command.lower().strip()

    for pattern in TARGET_PATTERNS:

        match = re.search(
            pattern,
            command,
        )

        if match:

            candidate = match.group(1).strip()

            candidate = (
                candidate
                .rstrip(".")
                .rstrip("?")
                .strip()
            )

            candidate = normalize_target_text(
                candidate
            )

            return candidate

    return None

def resolve_project_target_with_ambiguity(text):
    """
    Resolve a project target while preserving ambiguity.

    Returns:

        {
            "status": "resolved",
            "target": {...},
        }

    or:

        {
            "status": "ambiguous",
            "candidates": [...],
        }

    or:

        {
            "status": "not_found",
        }
    """

    function_matches = find_function_target(
        text
    )

    if len(function_matches) == 1:

        match = function_matches[0]

        return {
            "status": "resolved",
            "target": {
                "type": "function",
                "file": match["file"],
                "function": match["function"],
            },
        }

    if len(function_matches) > 1:

        return {
            "status": "ambiguous",
            "candidates": [
                {
                    "type": "function",
                    "file": match["file"],
                    "function": match["function"],
                }
                for match in function_matches
            ],
        }

    file_matches = find_file_target(
        text
    )

    if len(file_matches) == 1:

        return {
            "status": "resolved",
            "target": {
                "type": "file",
                "file": file_matches[0]["file"],
            },
        }

    if len(file_matches) > 1:

        return {
            "status": "ambiguous",
            "candidates": [
                {
                    "type": "file",
                    "file": match["file"],
                }
                for match in file_matches
            ],
        }

    return {
        "status": "not_found",
    }

def resolve_impact_target(command):
    """
    Extract and resolve the target from an
    impact-analysis command.
    """

    candidate = extract_target_candidate(
        command
    )

    if candidate is None:
        return {
            "status": "not_found",
        }

    return resolve_project_target_with_ambiguity(
        candidate
    )

def find_function_target(function_name):
    """
    Find project functions matching a function name.
    """

    index = get_project_analysis_index()

    matches = []

    for (
        file_path,
        symbol_name,
    ) in index["symbols"]:

        if symbol_name.lower() != function_name.lower():
            continue

        matches.append(
            {
                "file": file_path,
                "function": symbol_name,
            }
        )

    return matches


def find_file_target(filename):
    """
    Find project files matching a filename.
    """

    index = get_project_analysis_index()

    query = normalize_target_text(
        filename
    )

    normalized_query = _normalize_identifier(
        query
    )

    matches = []

    for file_path in index["files"]:

        actual_name = Path(
            file_path
        ).name

        normalized_name = (
            _normalize_identifier(
                actual_name
            )
        )

        if normalized_name == normalized_query:

            matches.append(
                {
                    "file": file_path,
                }
            )

    return matches


def resolve_project_target(text):
    """
    Resolve a user-provided target against the project index.

    Returns:
        {
            "type": "function" | "file",
            "file": "...",
            "function": "..."
        }

    or None if no target can be resolved.
    """

    text = text.lower().strip()

    function_matches = find_function_target(
        text
    )

    if len(function_matches) == 1:

        match = function_matches[0]

        return {
            "type": "function",
            "file": match["file"],
            "function": match["function"],
        }

    file_matches = find_file_target(
        text
    )

    if len(file_matches) == 1:

        return {
            "type": "file",
            "file": file_matches[0]["file"],
        }

    return None

def normalize_target_text(text):
    """
    Normalize natural-language and spoken programming
    terminology into a form suitable for project lookup.
    """

    text = text.lower().strip()

    replacements = {
        " underscore ": "_",
        " dot ": ".",
        " slash ": "/",
        " backslash ": "\\",
        " hyphen ": "-",
    }

    for spoken, symbol in replacements.items():
        text = text.replace(
            spoken,
            symbol,
        )

    text = text.replace(
        "the ",
        "",
    )

    text = " ".join(
        text.split()
    )

    # Convert spaces between words into underscores.
    text = text.replace(
        " ",
        "_",
    )

    # Remove accidental repeated underscores.
    text = re.sub(
        r"_+",
        "_",
        text,
    )

    return text