from pathlib import Path

from services.project_service import (
    _project_files,
)

_last_project_snapshot = None

def get_project_state():
    """
    Return the current high-level state of the project.

    Project discovery is delegated to the existing
    project service so this layer does not duplicate
    filesystem scanning logic.
    """

    files = [
        str(Path(path).resolve())
        for path in _project_files()
    ]

    python_files = [
        path
        for path in files
        if path.lower().endswith(".py")
    ]

    root = None

    if files:
        paths = [
            Path(path)
            for path in files
        ]

        try:
            root = str(
                Path(
                    Path(paths[0]).anchor
                )
            )

            common_root = Path(
                paths[0]
            )

            for path in paths[1:]:
                while (
                    common_root != common_root.parent
                    and common_root not in path.parents
                    and common_root != path
                ):
                    common_root = common_root.parent

            root = str(
                common_root.resolve()
            )

        except OSError:
            root = None

    return {
        "root": root,
        "files": sorted(files),
        "python_files": sorted(python_files),
        "file_count": len(files),
        "python_file_count": len(
            python_files
        ),
    }

def get_project_snapshot():
    """
    Return a lightweight snapshot of the current project files.

    Each file is represented by its filesystem signature so
    changes can be detected without reading the file contents.
    """

    files = {}

    for path in _project_files():

        path = Path(path)

        try:
            stat = path.stat()
        except OSError:
            continue

        files[str(path.resolve())] = (
            stat.st_mtime_ns,
            stat.st_size,
        )

    return {
        "files": files,
    }


def compare_project_snapshots(
    previous,
    current,
):
    """
    Compare two project snapshots.

    Returns files that were:
    - added
    - modified
    - deleted
    """

    previous_files = previous.get(
        "files",
        {},
    )

    current_files = current.get(
        "files",
        {},
    )

    previous_paths = set(
        previous_files
    )

    current_paths = set(
        current_files
    )

    added = sorted(
        current_paths - previous_paths
    )

    deleted = sorted(
        previous_paths - current_paths
    )

    modified = sorted(
        path
        for path in (
            previous_paths
            & current_paths
        )
        if previous_files[path]
        != current_files[path]
    )

    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
    }

def refresh_project_analysis_if_changed():
    """
    Compare the current project snapshot with the previous snapshot.

    If project files changed, invalidate the cached project analysis
    index so it will be rebuilt on the next request.
    """

    global _last_project_snapshot

    current_snapshot = get_project_snapshot()

    if _last_project_snapshot is None:

        _last_project_snapshot = current_snapshot

        return {
            "changed": False,
            "changes": {
                "added": [],
                "modified": [],
                "deleted": [],
            },
        }

    changes = compare_project_snapshots(
        _last_project_snapshot,
        current_snapshot,
    )

    changed = any(
        changes.values()
    )

    if should_refresh_project_analysis(
        changes
    ):

        from services.project_analysis_index import (
            clear_project_analysis_index_cache,
        )

        clear_project_analysis_index_cache()

    _last_project_snapshot = current_snapshot

    return {
        "changed": changed,
        "changes": changes,
    }

def should_refresh_project_analysis(
    changes,
):
    """
    Determine whether project analysis must be
    refreshed based on detected file changes.

    Only Python file changes affect the static
    Python analysis index.
    """

    changed_files = (
        changes.get("added", [])
        + changes.get("modified", [])
        + changes.get("deleted", [])
    )

    return any(
        str(path).lower().endswith(".py")
        for path in changed_files
    )