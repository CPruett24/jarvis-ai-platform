"""Explicit, process-local authorization for read-only project inspection.

Registration is a trusted application/user action, never a model tool. Nothing
is inferred from cwd, memory, or workspace configuration. No config is written.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import stat
import threading


DEFAULT_ROOT = Path(__file__).resolve().parents[1]


class ProjectAccessError(ValueError):
    pass


@dataclass(frozen=True)
class AuthorizedProject:
    project_id: str
    root: Path
    revision: int


_lock = threading.RLock()
_revision = 1
_projects = {"jarvis": AuthorizedProject("jarvis", DEFAULT_ROOT, _revision)}
_active = "jarvis"


def _reject_links(path):
    for component in reversed((path, *path.parents)):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ProjectAccessError("Symlink or reparse-point traversal is denied.")


def register_project(project_id, root):
    """Explicitly authorize a root. Call only from trusted user-facing setup."""
    global _revision
    if not isinstance(project_id, str) or not project_id.strip() or project_id == "jarvis":
        raise ProjectAccessError("A unique non-default project ID is required.")
    path = Path(root)
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise ProjectAccessError("A local absolute project root is required.")
    _reject_links(path)
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise ProjectAccessError("Project root is not a directory.")
    with _lock:
        _revision += 1
        context = AuthorizedProject(project_id, path, _revision)
        _projects[project_id] = context
        return context


def select_project(project_id):
    global _active
    with _lock:
        context = get_project(project_id)
        _active = context.project_id
        return context


def revoke_project(project_id):
    global _active, _revision
    if project_id == "jarvis":
        raise ProjectAccessError("The default project cannot be revoked.")
    with _lock:
        _projects.pop(project_id, None)
        _revision += 1
        if _active == project_id:
            _active = "jarvis"


def get_project(project_id=None):
    with _lock:
        context = _projects.get(project_id or _active)
        if context is None:
            raise ProjectAccessError("Project is not authorized.")
        return context


def list_projects():
    """Discover only deliberately authorized projects; never scan other roots."""
    with _lock:
        return tuple(_projects[key] for key in sorted(_projects))


def validate_project(context):
    if get_project(context.project_id) != context:
        raise ProjectAccessError("Project authorization is stale.")
    _reject_links(context.root)
    return context


def require_legacy_project():
    """Unmigrated relationship analyzers only support the default project."""
    context = get_project()
    if context.project_id != "jarvis":
        raise ProjectAccessError("Legacy relationship analysis is unavailable for additional projects.")
    return validate_project(context)


def resolve_project_path(context, target):
    validate_project(context)
    text = os.fspath(target)
    normalized = text.replace("\\", "/")
    if (not text or normalized.startswith("//") or "\x00" in text
            or ".." in normalized.split("/") or ":" in normalized
            or normalized.startswith("/")):
        raise ProjectAccessError("Unsafe project path is denied.")
    path = context.root.joinpath(*normalized.split("/"))
    _reject_links(path)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(context.root):
        raise ProjectAccessError("Path is outside the authorized project.")
    return resolved
