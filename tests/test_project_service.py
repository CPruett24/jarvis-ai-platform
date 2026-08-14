from services.project_service import (
    get_project_state,
    format_project_state,
)

from services.project_context import (
    get_full_project_context,
)


def test_project_state_contains_project_name():

    state = get_project_state()

    assert state["project_name"] == "JARVIS-AI"


def test_project_state_contains_files():

    state = get_project_state()

    assert state["file_count"] > 0


def test_project_state_contains_expected_directories():

    state = get_project_state()

    directories = state["directories"]

    assert "commands" in directories
    assert "models" in directories
    assert "services" in directories
    assert "tests" in directories


def test_project_state_contains_router():

    state = get_project_state()

    command_files = state["directories"]["commands"]

    assert any(
        file.replace("\\", "/") == "commands/router.py"
        for file in command_files
    )


def test_project_state_excludes_virtual_environment():

    state = get_project_state()

    for files in state["directories"].values():

        for file in files:

            assert ".venv" not in file
            assert "venv" not in file
            assert "__pycache__" not in file


def test_project_state_can_be_formatted():

    state = get_project_state()

    formatted = format_project_state(state)

    assert "JARVIS-AI" in formatted
    assert "commands/router.py" in formatted
    assert "services" in formatted

def test_full_project_context_contains_project_state():

    context = get_full_project_context(
        "How should we improve the code assistant?"
    )

    assert "CURRENT PROJECT STATE" in context
    assert "services/code_assistant.py" in context


def test_full_project_context_knows_intent_resolver_exists():

    context = get_full_project_context(
        "Should we create an intent resolver?"
    )

    assert "services/intent_resolver.py" in context