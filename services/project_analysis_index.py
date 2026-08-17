from pathlib import Path
from functools import lru_cache

from services.project_service import _project_files
from services.project_analysis_cache import get_source_tree
from services.project_execution import (
    _extract_functions,
    _extract_imports,
    _extract_calls,
    _resolve_call,
    _normalize_path,
)


def build_project_analysis_index():
    """
    Build a project-wide static analysis index.

    Each Python file is analyzed once.

    The resulting index contains:
    - functions
    - classes
    - imports
    - resolved calls
    - reverse call relationships
    """

    index = {
        "files": {},
        "symbols": {},
        "calls": {},
        "reverse_calls": {},
    }

    for file_path in _project_files():

        if file_path.suffix.lower() != ".py":
            continue

        tree = get_source_tree(file_path)

        if tree is None:
            continue

        functions = _extract_functions(tree)
        imports = _extract_imports(tree)

        normalized_file = _normalize_path(file_path)

        file_data = {
            "path": normalized_file,
            "functions": {},
            "imports": imports,
        }

        for function_name, function_node in functions.items():

            calls = _extract_calls(function_node)

            resolved_calls = []

            for call in calls:

                resolved = _resolve_call(
                    call,
                    functions,
                    imports,
                )

                if resolved is None:
                    continue

                resolved_calls.append(
                    {
                        "call": call,
                        "target": resolved,
                    }
                )

            file_data["functions"][
                function_name
            ] = {
                "name": function_name,
                "calls": calls,
                "resolved_calls": resolved_calls,
            }

            symbol_key = (
                normalized_file,
                function_name,
            )

            index["symbols"][
                symbol_key
            ] = {
                "file": normalized_file,
                "function": function_name,
            }

            caller_key = symbol_key

            index["calls"][
                caller_key
            ] = resolved_calls

            for resolved in resolved_calls:

                target = resolved["target"]

                if target["kind"] == "local":

                    target_file = normalized_file

                elif target["kind"] == "project_function":

                    target_file = _normalize_path(
                        target["path"]
                    )

                else:
                    continue

                target_key = (
                    target_file,
                    target["function"],
                )

                index["reverse_calls"].setdefault(
                    target_key,
                    [],
                )

                caller = {
                    "file": normalized_file,
                    "function": function_name,
                    "call": resolved["call"],
                }

                if caller not in index[
                    "reverse_calls"
                ][target_key]:

                    index[
                        "reverse_calls"
                    ][target_key].append(
                        caller
                    )

        index["files"][
            normalized_file
        ] = file_data

    return index

def _project_signature():
    """
    Build a signature for the current Python project files.

    The signature changes when a Python file is added, removed,
    modified, or resized.
    """

    files = []

    for path in _project_files():

        if path.suffix.lower() != ".py":
            continue

        try:
            stat = path.stat()

        except OSError:
            continue

        files.append(
            (
                str(path.resolve()),
                stat.st_mtime_ns,
                stat.st_size,
            )
        )

    return tuple(
        sorted(files)
    )


@lru_cache(maxsize=4)
def _get_cached_project_analysis_index(
    signature,
):
    """
    Return a cached project-wide analysis index.
    """

    return build_project_analysis_index()


def get_project_analysis_index():
    """
    Return the current project analysis index.

    The index is rebuilt automatically when Python project
    files change.
    """

    signature = _project_signature()

    return _get_cached_project_analysis_index(
        signature
    )


def clear_project_analysis_index_cache():
    """
    Clear the cached project analysis index.
    """

    _get_cached_project_analysis_index.cache_clear()


def get_project_analysis_index_cache_info():
    """
    Return cache statistics for the project analysis index.
    """

    return (
        _get_cached_project_analysis_index.cache_info()
    )

def find_indexed_function_callers(
    index,
    filename,
    function_name,
):
    """
    Find callers using a previously-built project index.
    """

    matches = [
        path
        for path in index["files"]
        if Path(path).name.lower()
        == filename.lower()
    ]

    if not matches:
        return None

    target_file = matches[0]

    target_key = (
        target_file,
        function_name,
    )

    callers = index[
        "reverse_calls"
    ].get(
        target_key,
        [],
    )

    return {
        "file": target_file,
        "function": function_name,
        "callers": callers,
    }