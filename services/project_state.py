from pathlib import Path

from services.project_service import (
    _project_files,
)


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