from pathlib import Path
import re

from services.project_service import (
    get_project_state,
    format_project_state,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

MASTER_PLAN = DOCS_DIR / "Jarvis_Master_Plan.md"
ROADMAP = DOCS_DIR / "ROADMAP.md"


def read_document(path):
    """Read a project document and return its contents."""

    if not path.exists():
        return ""

    try:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception as e:

        print(
            f"[Project Context] Failed to read {path}: {e}"
        )

        return ""


def _normalize(text):
    """Normalize text for lightweight keyword matching."""

    return re.sub(
        r"[^a-z0-9\s]",
        " ",
        text.lower(),
    )


def _tokenize(text):
    """Convert text into normalized searchable tokens."""

    return {
        token
        for token in _normalize(text).split()
        if len(token) > 2
    }


def _split_sections(document):
    """
    Split a Markdown document into logical sections.

    Each section begins at a Markdown heading and continues
    until the next heading of the same or higher level.
    """

    lines = document.splitlines()

    sections = []

    current_title = None
    current_level = None
    current_lines = []

    for line in lines:

        heading = re.match(
            r"^(#{1,6})\s+(.+?)\s*$",
            line,
        )

        if heading:

            level = len(heading.group(1))
            title = heading.group(2).strip()

            if current_title is not None:

                sections.append(
                    {
                        "title": current_title,
                        "level": current_level,
                        "content": "\n".join(
                            current_lines
                        ).strip(),
                    }
                )

            current_title = title
            current_level = level
            current_lines = []

            continue

        if current_title is not None:

            current_lines.append(line)

    if current_title is not None:

        sections.append(
            {
                "title": current_title,
                "level": current_level,
                "content": "\n".join(
                    current_lines
                ).strip(),
            }
        )

    return sections


def _score_section(section, query):
    """
    Score a documentation section against the user's question.

    This is intentionally lightweight. We are not introducing
    embeddings or another external dependency yet.
    """

    query_tokens = _tokenize(query)

    title_tokens = _tokenize(
        section["title"]
    )

    content_tokens = _tokenize(
        section["content"]
    )

    score = 0

    # Title matches are more important than body matches.

    score += len(
        query_tokens.intersection(title_tokens)
    ) * 5

    score += len(
        query_tokens.intersection(content_tokens)
    )

    query_lower = query.lower()

    # ---------------------------------------------------------
    # Roadmap / future-direction questions
    # ---------------------------------------------------------

    roadmap_phrases = {
        "next",
        "roadmap",
        "future",
        "major capability",
        "what comes next",
        "what should we build",
        "long term",
        "long-term",
    }

    if any(
        phrase in query_lower
        for phrase in roadmap_phrases
    ):

        title_lower = section["title"].lower()

        if any(
            phrase in title_lower
            for phrase in (
                "current roadmap",
                "phase 3",
                "phase 4",
                "phase 5",
                "current priority",
                "future vision",
            )
        ):

            score += 15

    # ---------------------------------------------------------
    # Architecture questions
    # ---------------------------------------------------------

    architecture_phrases = {
        "architecture",
        "design",
        "structure",
        "modular",
        "separation",
        "refactor",
        "engineering",
        "principle",
    }

    if any(
        phrase in query_lower
        for phrase in architecture_phrases
    ):

        title_lower = section["title"].lower()

        if any(
            phrase in title_lower
            for phrase in (
                "architecture",
                "engineering principles",
                "coding standards",
                "core philosophy",
                "current project structure",
            )
        ):

            score += 15

    # ---------------------------------------------------------
    # Code assistant questions
    # ---------------------------------------------------------

    code_phrases = {
        "code",
        "file",
        "function",
        "class",
        "bug",
        "review",
        "multi file",
        "multi-file",
        "developer",
        "software",
    }

    if any(
        phrase in query_lower
        for phrase in code_phrases
    ):

        title_lower = section["title"].lower()

        if any(
            phrase in title_lower
            for phrase in (
                "ai code assistant",
                "multi-file understanding",
                "code review",
                "developer assistant",
            )
        ):

            score += 12

    return score


def get_relevant_project_context(
    question,
    max_sections=5,
):
    """
    Retrieve the most relevant project documentation
    for a specific question.
    """

    documents = [
        (
            "JARVIS MASTER PLAN",
            MASTER_PLAN,
        ),
        (
            "JARVIS ROADMAP",
            ROADMAP,
        ),
    ]

    all_sections = []

    for document_name, path in documents:

        content = read_document(path)

        if not content:
            continue

        sections = _split_sections(content)

        for section in sections:

            section["document"] = document_name

            all_sections.append(section)

    if not all_sections:

        return ""

    scored_sections = []

    for section in all_sections:

        score = _score_section(
            section,
            question,
        )

        scored_sections.append(
            (
                score,
                section,
            )
        )

    scored_sections.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected = [
        section
        for score, section in scored_sections
        if score > 0
    ][:max_sections]

    # If nothing matched, provide the most useful
    # high-level project sections as a fallback.

    if not selected:

        fallback_titles = {
            "Vision",
            "Current Architecture",
            "Current Roadmap",
            "Engineering Principles",
            "Current Priority",
        }

        selected = [
            section
            for section in all_sections
            if section["title"] in fallback_titles
        ][:max_sections]

    context_parts = []

    for section in selected:

        context_parts.append(
            f"===== {section['document']} =====\n"
            f"## {section['title']}\n\n"
            f"{section['content']}"
        )

    return "\n\n".join(context_parts)


def get_project_context():
    """
    Backwards-compatible helper that returns the full
    project documentation.

    New reasoning code should prefer
    get_relevant_project_context().
    """

    return get_relevant_project_context(
        "JARVIS architecture roadmap vision",
        max_sections=10,
    )

def get_full_project_context(question):
    """
    Build the complete reasoning context for a project-aware question.

    This combines relevant project documentation with the actual
    current project state.
    """

    documentation = get_relevant_project_context(
        question
    )

    state = get_project_state()

    project_state = format_project_state(
        state
    )

    context_parts = []

    if documentation:

        context_parts.append(
            "===== RELEVANT PROJECT DOCUMENTATION =====\n"
            + documentation
        )

    if project_state:

        context_parts.append(
            "===== CURRENT PROJECT STATE =====\n"
            + project_state
        )

    return "\n\n".join(
        context_parts
    )