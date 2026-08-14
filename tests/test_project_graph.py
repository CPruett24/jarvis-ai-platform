from services.project_graph import (
    build_dependency_graph,
    get_dependency_tree,
    get_file_dependents,
    format_dependency_tree,
)


def test_dependency_graph_contains_router():

    graph = build_dependency_graph()

    router_paths = [
        path
        for path in graph
        if path.endswith("commands/router.py")
    ]

    assert router_paths


def test_router_has_dependencies():

    graph = build_dependency_graph()

    router_path = next(
        path
        for path in graph
        if path.endswith("commands/router.py")
    )

    dependencies = graph[router_path]["dependencies"]

    assert any(
        path.endswith("services/ai_service.py")
        for path in dependencies
    )

    assert any(
        path.endswith("commands/tool_manager.py")
        for path in dependencies
    )


def test_dependency_graph_tracks_dependents():

    dependents = get_file_dependents(
        "tool_manager.py"
    )

    assert dependents is not None

    assert any(
        path.endswith("commands/router.py")
        for path in dependents
    )


def test_dependency_tree_contains_router():

    tree = get_dependency_tree(
        "router.py"
    )

    assert tree is not None

    assert tree["file"].endswith(
        "commands/router.py"
    )


def test_dependency_tree_contains_children():

    tree = get_dependency_tree(
        "router.py"
    )

    assert tree is not None

    dependencies = tree["dependencies"]

    assert any(
        dependency["file"].endswith(
            "services/ai_service.py"
        )
        for dependency in dependencies
    )


def test_dependency_tree_respects_depth():

    tree = get_dependency_tree(
        "router.py",
        max_depth=1,
    )

    assert tree is not None

    assert tree["depth"] == 0

    for dependency in tree["dependencies"]:

        assert dependency["depth"] == 1

        assert dependency["dependencies"] == []


def test_dependency_tree_can_be_formatted():

    tree = get_dependency_tree(
        "router.py"
    )

    formatted = format_dependency_tree(
        tree
    )

    assert formatted is not None

    assert "commands/router.py" in formatted

    assert "services/ai_service.py" in formatted


def test_unknown_file_returns_none():

    tree = get_dependency_tree(
        "does_not_exist.py"
    )

    assert tree is None

def test_default_graph_excludes_tests():

    graph = build_dependency_graph()

    assert not any(
        "/tests/" in path.replace("\\", "/")
        for path in graph
    )


def test_graph_can_include_tests():

    graph = build_dependency_graph(
        include_tests=True
    )

    assert any(
        "/tests/" in path.replace("\\", "/")
        for path in graph
    )