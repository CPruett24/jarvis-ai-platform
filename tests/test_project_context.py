from services.project_context import (
    get_relevant_project_context,
)


def test_roadmap_question_retrieves_multi_file_context():

    context = get_relevant_project_context(
        "What is the next major capability this project is supposed to implement?"
    )

    assert "Multi-File Understanding" in context


def test_architecture_question_retrieves_engineering_principles():

    context = get_relevant_project_context(
        "Would you keep this design based on the project's architecture?"
    )

    assert (
        "Engineering Principles" in context
        or "Core Philosophy" in context
        or "Current Architecture" in context
    )


def test_code_question_retrieves_code_assistant_context():

    context = get_relevant_project_context(
        "How should we improve the code assistant?"
    )

    assert (
        "AI Code Assistant" in context
        or "Developer Assistant" in context
    )


def test_unknown_question_returns_context():

    context = get_relevant_project_context(
        "Tell me something about JARVIS."
    )

    assert context