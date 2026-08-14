from services.project_dependencies import (
    get_file_dependencies,
)

from services.project_service import (
    _project_files,
    classify_project_file,
)


def _normalize_path(path):
    """
    Normalize a filesystem path for consistent graph keys.
    """

    return path.replace("\\", "/")


def build_dependency_graph(
    include_tests=False,
):
    """
    Build a project-wide dependency graph.

    Each project file is represented as a graph node.
    Each import between project files becomes a directed edge.
    """

    from services.project_service import _project_files

    graph = {}

    project_files = [
    path
    for path in _project_files()
    if include_tests
    or classify_project_file(path) != "test"
    ]

    for file in project_files:

        normalized_file = _normalize_path(
            str(file)
        )

        graph[normalized_file] = {
            "dependencies": [],
            "dependents": [],
        }

    for file in project_files:

        normalized_file = _normalize_path(
            str(file)
        )

        result = get_file_dependencies(
            file.name
        )

        if result is None:
            continue

        for dependency in result["dependencies"]:

            dependency_path = _normalize_path(
                dependency["path"]
            )

            if dependency_path not in graph:
                continue

            if dependency_path not in graph[normalized_file]["dependencies"]:

                graph[normalized_file]["dependencies"].append(
                    dependency_path
                )

            if normalized_file not in graph[dependency_path]["dependents"]:

                graph[dependency_path]["dependents"].append(
                    normalized_file
                )

    return graph


def get_dependency_tree(
    filename,
    max_depth=3,
):
    """
    Return the dependency tree for a specific file.

    The traversal is depth-limited and cycle-safe.
    """

    from services.project_service import find_matching_files

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    root = _normalize_path(
        str(matches[0])
    )

    graph = build_dependency_graph()

    if root not in graph:
        return None

    def walk(
        current,
        depth,
        visited,
    ):

        node = {
            "file": current,
            "depth": depth,
            "dependencies": [],
        }

        if depth >= max_depth:
            return node

        if current in visited:
            return node

        visited.add(current)

        for dependency in graph[current]["dependencies"]:

            child = walk(
                dependency,
                depth + 1,
                visited.copy(),
            )

            node["dependencies"].append(
                child
            )

        return node

    return walk(
        root,
        0,
        set(),
    )


def get_file_dependents(filename):
    """
    Return files that directly depend on the supplied file.
    """

    from services.project_service import find_matching_files

    matches = find_matching_files(
        filename
    )

    if not matches:
        return None

    file_path = _normalize_path(
        str(matches[0])
    )

    graph = build_dependency_graph()

    if file_path not in graph:
        return None

    return graph[file_path]["dependents"]


def format_dependency_tree(
    tree,
):
    """
    Convert a dependency tree into readable text.
    """

    if tree is None:
        return None

    lines = []

    def walk(node):

        indentation = "  " * node["depth"]

        lines.append(
            f"{indentation}- {node['file']}"
        )

        for dependency in node["dependencies"]:

            walk(dependency)

    walk(tree)

    return "\n".join(lines)