from services.project_analysis_index import (
    get_project_analysis_index,
    _normalize_path,
)

from services.project_target import resolve_impact_target


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

def analyze_file_impact(
    filename,
):
    """
    Analyze project-level impact of changing a file.

    Determines:
    - functions defined in the file
    - direct callers of those functions
    - project functions called by those functions
    - project files depended on by the target file
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

    # ---------------------------------------------------------
    # Functions defined in the target file
    # ---------------------------------------------------------

    defined_functions = [
        function_name
        for file_path, function_name
        in index["symbols"]
        if (
            file_path == target_file
            and function_name != "<module>"
        )
    ]

    # ---------------------------------------------------------
    # Direct callers of functions in the target file
    # ---------------------------------------------------------

    callers = []

    for function_name in defined_functions:

        key = (
            target_file,
            function_name,
        )

        for caller in index["reverse_calls"].get(
            key,
            [],
        ):

            callers.append(
                {
                    "file": caller["file"],
                    "function": caller["function"],
                    "target_function": function_name,
                }
            )

    # Remove duplicate caller relationships.

    unique_callers = {}

    for caller in callers:

        key = (
            caller["file"],
            caller["function"],
            caller["target_function"],
        )

        unique_callers[key] = caller

    callers = list(
        unique_callers.values()
    )

    # ---------------------------------------------------------
    # Outbound project dependencies
    # ---------------------------------------------------------

    outbound_calls = []

    for function_name in defined_functions:

        function_calls = index["calls"].get(
            (
                target_file,
                function_name,
            ),
            [],
        )

        outbound_calls.extend(
            function_calls
        )

    dependencies = []

    for resolved in outbound_calls:

        target = resolved.get(
            "target"
        )

        if not target:
            continue

        if target.get("kind") != "project_function":
            continue

        dependency_file = target.get(
            "path"
        )

        if not dependency_file:
            continue

        dependency_file = _normalize_path(
            dependency_file
        )

        if dependency_file == target_file:
            continue

        if dependency_file not in dependencies:

            dependencies.append(
                dependency_file
            )

    return {
        "target": {
            "file": target_file,
        },
        "defined_functions": sorted(
            defined_functions
        ),
        "callers": sorted(
            callers,
            key=lambda item: (
                item["file"],
                item["function"],
                item["target_function"],
            ),
        ),
        "dependencies": sorted(
            dependencies
        ),
    }

def explain_function_impact(command):
    """
    Resolve an impact-analysis request and return
    structured data suitable for AI reasoning.
    """

    target_result = resolve_impact_target(
        command
    )

    if target_result["status"] == "not_found":

        return {
            "status": "not_found",
            "message": (
                "I could not identify a specific "
                "project function or file from that request."
            ),
        }

    if target_result["status"] == "ambiguous":

        return {
            "status": "ambiguous",
            "candidates": target_result[
                "candidates"
            ],
        }

    target = target_result["target"]

    if target["type"] == "function":

        analysis = analyze_function_impact(
            target["file"],
            target["function"],
        )

        if analysis is None:

            return {
                "status": "not_found",
                "message": (
                    "I found the target, but could "
                    "not analyze its project impact."
                ),
            }

        return {
            "status": "resolved",
            "target": target,
            "analysis": analysis,
        }

    analysis = analyze_file_impact(
        target["file"]
    )

    if analysis is None:

        return {
            "status": "not_found",
            "message": (
                "I found the file, but could "
                "not analyze its project impact."
            ),
        }

    return {
        "status": "resolved",
        "target": target,
        "analysis": analysis,
    }