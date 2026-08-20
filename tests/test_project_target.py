from services.project_target import (
    find_function_target,
    find_file_target,
    resolve_project_target,
    resolve_project_target_with_ambiguity,
)

from services.project_target import (
    extract_target_candidate,
    resolve_impact_target,
    normalize_target_text,
)


def test_find_execute_tool():

    matches = find_function_target(
        "execute_tool"
    )

    assert any(
        match["file"].endswith(
            "commands/tool_manager.py"
        )
        and match["function"]
        == "execute_tool"
        for match in matches
    )


def test_find_router_file():

    matches = find_file_target(
        "router.py"
    )

    assert any(
        match["file"].endswith(
            "commands/router.py"
        )
        for match in matches
    )


def test_resolve_execute_tool():

    result = resolve_project_target(
        "execute_tool"
    )

    assert result is not None
    assert result["type"] == "function"
    assert result["function"] == "execute_tool"
    assert result["file"].endswith(
        "commands/tool_manager.py"
    )


def test_resolve_router_file():

    result = resolve_project_target(
        "router.py"
    )

    assert result is not None
    assert result["type"] == "file"
    assert result["file"].endswith(
        "commands/router.py"
    )

def test_extract_function_from_impact_question():

    result = extract_target_candidate(
        "what would be affected if I change execute_tool?"
    )

    assert result == "execute_tool"


def test_extract_file_from_impact_question():

    result = extract_target_candidate(
        "what would break if I modify router.py?"
    )

    assert result == "router.py"


def test_resolve_impact_function():

    result = resolve_impact_target(
        "what would be affected if I change execute_tool?"
    )

    assert result["status"] == "resolved"

    assert (
        result["target"]["function"]
        == "execute_tool"
    )


def test_resolve_impact_file():

    result = resolve_impact_target(
        "what would break if I modify router.py?"
    )

    assert result["status"] == "resolved"

    assert result["target"]["type"] == "file"


def test_unknown_impact_target():

    result = resolve_impact_target(
        "what would break if I modify imaginary_function?"
    )

    assert result["status"] == "not_found"

def test_ambiguous_target_is_not_guessed(monkeypatch):

    from services import project_target

    monkeypatch.setattr(
        project_target,
        "find_function_target",
        lambda name: [
            {
                "file": "C:/project/a.py",
                "function": "process",
            },
            {
                "file": "C:/project/b.py",
                "function": "process",
            },
        ],
    )

    result = (
        project_target
        .resolve_project_target_with_ambiguity(
            "process"
        )
    )

    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2

def test_ambiguous_target_is_not_guessed(monkeypatch):

    from services import project_target

    monkeypatch.setattr(
        project_target,
        "find_function_target",
        lambda name: [
            {
                "file": "C:/project/a.py",
                "function": "process",
            },
            {
                "file": "C:/project/b.py",
                "function": "process",
            },
        ],
    )

    result = (
        project_target
        .resolve_project_target_with_ambiguity(
            "process"
        )
    )

    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2

def test_normalize_spoken_function_name():

    from services.project_target import (
        normalize_target_text,
    )

    assert (
        normalize_target_text(
            "execute tool"
        )
        == "execute_tool"
    )


def test_normalize_spoken_underscore():

    from services.project_target import (
        normalize_target_text,
    )

    assert (
        normalize_target_text(
            "execute underscore tool"
        )
        == "execute_tool"
    )


def test_normalize_spoken_filename():

    from services.project_target import (
        normalize_target_text,
    )

    assert (
        normalize_target_text(
            "router dot py"
        )
        == "router.py"
    )

def test_normalize_project_service_filename():

    assert (
        normalize_target_text(
            "project underscore service dot py"
        )
        == "project_service.py"
    )


def test_find_file_target_accepts_camel_case():

    matches = find_file_target(
        "projectService.py"
    )

    assert len(matches) == 1

    assert (
        matches[0]["file"]
        .lower()
        .endswith(
            "services/project_service.py"
        )
    )