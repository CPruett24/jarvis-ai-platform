from services.project_analysis_index import (
    get_project_analysis_index,
)


def analyze_function_impact(
    filename,
    function_name,
    max_depth=3,
):
    """
    Analyze project functions that may be affected
    by changes to the specified function.

    Uses the cached project analysis index.
    """

    index = get_project_analysis_index()

    matches = [
        path
        for path in index["files"]
        if path.lower().endswith(
            filename.lower()
        )
    ]

    if not matches:
        return None

    target_file = matches[0]

    target_key = (
        target_file,
        function_name,
    )

    if target_key not in index["symbols"]:
        return None

    visited = set()

    def walk(
        file_path,
        function,
        depth,
    ):

        key = (
            file_path,
            function,
        )

        node = {
            "file": file_path,
            "function": function,
            "depth": depth,
            "callers": [],
        }

        if key in visited:
            return node

        visited.add(key)

        if depth >= max_depth:
            return node

        callers = index[
            "reverse_calls"
        ].get(
            key,
            [],
        )

        for caller in callers:

            child = walk(
                caller["file"],
                caller["function"],
                depth + 1,
            )

            node["callers"].append(
                child
            )

        return node

    return {
        "target": {
            "file": target_file,
            "function": function_name,
        },
        "impact": walk(
            target_file,
            function_name,
            0,
        ),
    }

def format_function_impact(
    analysis,
):
    """
    Format function impact analysis
    for human-readable output.
    """

    if analysis is None:
        return "No matching function found."

    target = analysis["target"]

    lines = [
        f"Impact Analysis: "
        f"{target['file']}::{target['function']}()"
    ]

    def walk(node, prefix=""):

        for caller in node["callers"]:

            lines.append(
                f"{prefix}- "
                f"{caller['file']}::"
                f"{caller['function']}()"
            )

            walk(
                caller,
                prefix + "  ",
            )

    walk(
        analysis["impact"]
    )

    return "\n".join(lines)