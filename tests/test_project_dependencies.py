from services.project_dependencies import (
    get_file_dependencies,
)


def test_router_dependencies_are_detected():

    result = get_file_dependencies(
        "router.py"
    )

    assert result is not None

    modules = result["imports"]

    assert (
        "services.ai_service"
        in modules
    )

    assert (
        "commands.tool_manager"
        in modules
    )


def test_router_resolves_project_dependencies():

    result = get_file_dependencies(
        "router.py"
    )

    assert result is not None

    paths = [
        dependency["path"]
        for dependency in result["dependencies"]
    ]

    normalized_paths = [
        path.replace("\\", "/")
        for path in paths
    ]

    assert (
        any(
            path.endswith(
                "services/ai_service.py"
            )
            for path in normalized_paths
        )
    )


def test_external_imports_are_separated():

    result = get_file_dependencies(
        "router.py"
    )

    assert result is not None

    assert isinstance(
        result["external_imports"],
        list,
    )


def test_unknown_file_returns_none():

    result = get_file_dependencies(
        "does_not_exist.py"
    )

    assert result is None