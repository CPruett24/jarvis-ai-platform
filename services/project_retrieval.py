"""Bounded filesystem mechanics used by project_service, never an analysis engine."""
from contextlib import contextmanager
from datetime import datetime, UTC
import hashlib
import os
from pathlib import Path
import stat
import time

from models.source_evidence import RetrievalLimits, RetrievalResult, RetrievalStatus, SourceExcerpt
from services.project_access import get_project, validate_project, resolve_project_path, ProjectAccessError
from services.cancellation import check_cancelled, OperationCancelled

EXCLUDED_DIRECTORIES = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".idea", ".vscode", "node_modules", "build", "dist", "target", "coverage",
    ".aws", ".ssh", ".codex", ".agents", "data", "logs", ".next", "vendor",
})
SUPPORTED_EXTENSIONS = frozenset({".py", ".md", ".txt", ".json", ".yaml", ".yml",
    ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".toml", ".rs", ".go"})


def permitted(relative):
    path = Path(relative)
    parts = [part.lower() for part in path.parts]
    name = parts[-1] if parts else ""
    return bool(parts and not any(part in EXCLUDED_DIRECTORIES for part in parts)
        and not any(part.startswith(".") for part in parts)
        and not any(word in name for word in ("secret", "credential", "private_key"))
        and not name.startswith(("config.", "settings."))
        and name not in {"config.json", "settings.json", "workspaces.json", "config.yaml",
                         "config.yml", "config.toml", "settings.yaml", "settings.yml", "settings.toml",
                         "auth.json", "token.json", "tokens.json", "service-account.json",
                         "status.json", "runtime.json", "runtime_state.json"}
        and path.suffix.lower() in SUPPORTED_EXTENSIONS)


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self, limits, cancellation_event=None):
        self.limits = limits
        self.event = cancellation_event
        self.deadline = time.monotonic() + limits.seconds
        self.entries = 0
        self.bytes = 0

    def check(self):
        check_cancelled(self.event)
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("time")


@contextmanager
def locked_path(path, directory=False):
    """On Windows pin every ancestor against deletion/reparse replacement.

    No FILE_SHARE_DELETE: an adversarial directory swap cannot redirect the
    subsequently opened source. OPEN_REPARSE_POINT lets us reject links on the
    actual handles, not just a pre-open lstat. Locks live until read completes.
    """
    if os.name != "nt":
        # C1's supported deployment is Windows. Fail closed rather than claim
        # race-safe containment on an unimplemented platform.
        raise ProjectAccessError("C1 safe filesystem access requires Windows.")
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    class HandleInfo(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("creation", wintypes.FILETIME),
                   ("access", wintypes.FILETIME), ("write", wintypes.FILETIME),
                   ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
                   ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
                   ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]
    info_fn = kernel.GetFileInformationByHandle
    info_fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(HandleInfo)]
    handles = []
    try:
        for component in reversed((path, *path.parents)):
            is_dir = component != path or directory
            handle = create(str(component), 0 if is_dir else 0x80000000,
                            3 if is_dir else 1, None, 3, 0x00200000 | 0x02000000, None)
            if handle == wintypes.HANDLE(-1).value:
                raise OSError(ctypes.get_last_error(), f"Safe project open failed: {component}")
            handles.append(handle)
            info = HandleInfo()
            if not info_fn(handle, ctypes.byref(info)):
                raise OSError(ctypes.get_last_error(), "Cannot inspect project handle")
            if info.attributes & 0x400:
                raise ProjectAccessError("Reparse-point traversal is denied.")
            if not is_dir and info.links > 1:
                raise ProjectAccessError("Hard-linked source files are denied.")
        if directory:
            yield None
        else:
            import msvcrt
            fd = msvcrt.open_osfhandle(int(handles[-1]), os.O_RDONLY | os.O_BINARY)
            handles.pop()  # fd now owns this handle
            with os.fdopen(fd, "rb") as stream:
                yield stream
    finally:
        for handle in reversed(handles):
            close(handle)


def discover(context=None, *, recursive=True, limits=None, cancellation_event=None):
    context = context or get_project()
    limits = limits or RetrievalLimits()
    result = RetrievalResult(context.project_id, context.revision, "discover", RetrievalStatus.SUCCESS)
    budget = Budget(limits, cancellation_event)
    try:
        validate_project(context)
        pending = [context.root]
        while pending:
            budget.check()
            directory = pending.pop()
            with locked_path(directory, directory=True):
                with os.scandir(directory) as entries:
                    children = []
                    for entry in entries:
                        budget.check()
                        budget.entries += 1
                        if budget.entries > limits.max_entries:
                            raise BudgetExceeded("entries")
                        relative = Path(entry.path).relative_to(context.root)
                        if entry.name.startswith(".") or entry.name.lower() in EXCLUDED_DIRECTORIES:
                            continue
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                children.append(Path(entry.path))
                            else:
                                result.paths.append(relative.as_posix() + "/")
                        elif entry.is_file(follow_symlinks=False) and permitted(relative):
                            result.paths.append(relative.as_posix())
                    pending.extend(sorted(children, reverse=True))
        validate_project(context)
    except BudgetExceeded as exc:
        result.status = RetrievalStatus.PARTIAL if result.paths else RetrievalStatus.BUDGET_EXCEEDED
        result.limits_reached.append(str(exc))
    except OperationCancelled:
        result.status, result.paths = RetrievalStatus.CANCELLED, []
    except (ProjectAccessError, OSError) as exc:
        result.status, result.error, result.paths = RetrievalStatus.DENIED, str(exc), []
    result.entries_visited = budget.entries
    result.paths.sort(key=lambda value: (value.casefold(), value))
    return result


def read_source(target, context=None, *, start_line=1, limits=None, cancellation_event=None):
    context = context or get_project()
    limits = limits or RetrievalLimits()
    result = RetrievalResult(context.project_id, context.revision, "read", RetrievalStatus.SUCCESS)
    budget = Budget(limits, cancellation_event)
    try:
        budget.check()
        if type(start_line) is not int or start_line < 1:
            raise ValueError("Start line must be positive.")
        path = resolve_project_path(context, target)
        relative = path.relative_to(context.root).as_posix()
        if not permitted(relative):
            raise ProjectAccessError("File is excluded by the source-read policy.")
        with locked_path(path) as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ProjectAccessError("Only regular source files may be read.")
            if info.st_size > limits.max_file_bytes:
                raise BudgetExceeded("file_bytes")
            chunks = []
            while True:
                budget.check()
                chunk = stream.read(min(8192, limits.max_file_bytes + 1 - budget.bytes))
                if not chunk:
                    break
                chunks.append(chunk)
                budget.bytes += len(chunk)
                if budget.bytes > limits.max_file_bytes:
                    raise BudgetExceeded("file_bytes")
            data = b"".join(chunks)
        validate_project(context)
        if b"\x00" in data:
            raise ValueError("Binary source is unsupported.")
        text = data.decode("utf-8-sig", errors="strict")
        lines = text.splitlines()
        selected, size = [], 0
        for line in lines[start_line - 1:start_line - 1 + limits.max_lines]:
            budget.check()
            cost = len(line.encode("utf-8")) + 1
            if size + cost > limits.max_evidence_bytes:
                result.limits_reached.append("evidence_bytes")
                break
            selected.append(line)
            size += cost
        if not selected:
            result.status = RetrievalStatus.NOT_FOUND
            result.error = "No readable lines in the requested range."
            result.bytes_read = budget.bytes
            return result
        truncated = start_line > 1 or start_line - 1 + len(selected) < len(lines)
        if truncated:
            result.status = RetrievalStatus.PARTIAL
            result.limits_reached.append("line_range")
        excerpt_text = "\n".join(selected)
        digest = hashlib.sha256(data).hexdigest()
        source_id = "S" + hashlib.sha256(f"{context}:{relative}:{start_line}:{digest}".encode()).hexdigest()[:12]
        result.excerpts.append(SourceExcerpt(source_id, context.project_id, context.revision,
            relative, start_line, start_line + len(selected) - 1, excerpt_text,
            datetime.now(UTC).isoformat(), (info.st_mtime_ns, info.st_size), digest, truncated,
            "documentation" if path.suffix.lower() in {".md", ".txt"} else "source", len(lines)))
        result.paths = [relative]
    except FileNotFoundError:
        result.status, result.error = RetrievalStatus.NOT_FOUND, "File was not found."
    except ProjectAccessError as exc:
        result.status, result.error = RetrievalStatus.DENIED, str(exc)
    except BudgetExceeded as exc:
        result.status = RetrievalStatus.BUDGET_EXCEEDED
        result.limits_reached.append(str(exc))
    except OperationCancelled:
        result.status = RetrievalStatus.CANCELLED
    except (OSError, UnicodeError, ValueError) as exc:
        result.status, result.error = RetrievalStatus.READ_ERROR, str(exc)
    result.bytes_read = budget.bytes
    return result
