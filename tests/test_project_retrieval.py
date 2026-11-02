from dataclasses import replace
import threading
import pytest

from services import project_access as access
from services.project_retrieval import discover, read_source
from services.project_service import retrieve_project_sources
from models.source_evidence import RetrievalLimits, RetrievalStatus


@pytest.fixture
def project(tmp_path):
    projects, active, revision = access._projects.copy(), access._active, access._revision
    context = access.register_project("fixture", tmp_path)
    access.select_project("fixture")
    yield context
    access._projects, access._active, access._revision = projects, active, revision


def test_windows_safe_read_and_ranges(project):
    (project.root / "a.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    result = read_source("a.py", project, start_line=2, limits=RetrievalLimits(max_lines=1))
    assert result.status == RetrievalStatus.PARTIAL
    excerpt = result.excerpts[0]
    assert (excerpt.start_line, excerpt.end_line, excerpt.text) == (2, 2, "two")
    assert excerpt.digest and excerpt.project_id == "fixture"


@pytest.mark.parametrize("name", [".env", "secret.json", "credentials.yaml", "data/status.json",
    "data/jarvis.db", "node_modules/a.py", "build/a.py", ".git/a.py", "key.pem", "a.log"])
def test_exclusions_apply_to_discovery_and_explicit_reads(project, name):
    path = project.root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("secret", encoding="utf-8")
    assert not discover(project).paths
    result = read_source(name, project)
    assert result.status == RetrievalStatus.DENIED
    assert not result.excerpts


def test_duplicate_and_exact_path(project):
    for directory in ("a", "b"):
        (project.root / directory).mkdir()
        (project.root / directory / "router.py").write_text("route = True\n")
    result = retrieve_project_sources("router.py", context=project)
    assert result.status == RetrievalStatus.AMBIGUOUS
    assert result.candidates == ["a/router.py", "b/router.py"]
    assert retrieve_project_sources("a/router.py", context=project).success


def test_missing_oversized_invalid_encoding_and_cancellation(project):
    assert read_source("missing.py", project).status == RetrievalStatus.NOT_FOUND
    path = project.root / "a.py"
    path.write_bytes(b"x" * 100)
    result = read_source("a.py", project, limits=RetrievalLimits(max_file_bytes=10))
    assert result.status == RetrievalStatus.BUDGET_EXCEEDED and result.bytes_read == 0
    path.write_bytes(b"\xff")
    assert read_source("a.py", project).status == RetrievalStatus.READ_ERROR
    event = threading.Event()
    event.set()
    assert read_source("a.py", project, cancellation_event=event).status == RetrievalStatus.CANCELLED


def test_discovery_entry_limit_and_top_level(project):
    (project.root / "folder").mkdir()
    (project.root / "folder" / "a.py").write_text("value = 1\n")
    (project.root / "b.py").write_text("value = 2\n")
    assert discover(project, recursive=False).paths == ["b.py", "folder/"]
    assert "entries" in discover(project, limits=RetrievalLimits(max_entries=1)).limits_reached


def test_reparse_point_is_denied(project, tmp_path):
    target = project.root / "real.py"
    target.write_text("value = 1\n")
    link = project.root / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Windows account cannot create symlinks")
    assert read_source("link.py", project).status == RetrievalStatus.DENIED
    assert discover(project).paths == ["real.py"]


def test_search_uses_real_lines_and_refreshes(project):
    path = project.root / "history.py"
    path.write_text("def save_history():\n    return 1\n")
    first = retrieve_project_sources("conversation history", context=project, search=True)
    assert first.success and first.excerpts[0].start_line == 1
    path.write_text("def save_history():\n    return 2\n")
    second = retrieve_project_sources("conversation history", context=project, search=True)
    assert first.excerpts[0].digest != second.excerpts[0].digest


def test_hard_link_is_denied(project):
    import os
    path = project.root / "real.py"
    path.write_text("value = 1\n")
    os.link(path, project.root / "linked.py")
    assert read_source("linked.py", project).status == RetrievalStatus.DENIED


def test_reparse_policy_without_symlink_privileges(project, monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    (project.root / "a.py").write_text("pass\n")
    original = Path.lstat
    def lstat(path):
        if path == project.root / "a.py":
            return SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400)
        return original(path)
    monkeypatch.setattr(Path, "lstat", lstat)
    assert read_source("a.py", project).status == RetrievalStatus.DENIED


def test_search_budgets_are_enforced(project):
    for number in range(5):
        (project.root / f"history{number}.py").write_text("history = True\n" * 30)
    result = retrieve_project_sources("history", context=project, search=True,
        limits=RetrievalLimits(max_search_bytes=500, max_excerpts=1, max_lines=2, max_evidence_bytes=40))
    assert result.bytes_read <= 500
    assert len(result.excerpts) <= 1
    assert sum(len(e.text.encode()) for e in result.excerpts) <= 40
    assert all(e.end_line - e.start_line + 1 <= 2 for e in result.excerpts)


def test_incomplete_discovery_cannot_resolve_basename(project):
    (project.root / "router.py").write_text("pass\n")
    (project.root / "other.py").write_text("pass\n")
    result = retrieve_project_sources("router.py", context=project,
                                      limits=RetrievalLimits(max_entries=1))
    assert not result.success and not result.excerpts


def test_time_budget_is_checked_before_io(project, monkeypatch):
    from services import project_retrieval
    ticks = iter([0, 5])
    monkeypatch.setattr(project_retrieval.time, "monotonic", lambda: next(ticks))
    result = read_source("missing.py", project, limits=RetrievalLimits(seconds=1))
    assert result.status == RetrievalStatus.BUDGET_EXCEEDED and result.bytes_read == 0


def test_blank_lines_keep_exact_source_ranges(project):
    (project.root / "a.py").write_text("value = 1\n\n", encoding="utf-8")
    result = read_source("a.py", project)
    assert result.success
    assert result.excerpts[0].text == "value = 1\n"
    assert result.excerpts[0].end_line == result.excerpts[0].total_lines == 2
    blank = read_source("a.py", project, start_line=2)
    assert blank.success and blank.excerpts[0].text == ""
    assert blank.excerpts[0].start_line == blank.excerpts[0].end_line == 2


@pytest.mark.parametrize("outside", [False, True])
def test_physical_windows_junction_is_denied_by_policy_and_native_handles(project, outside):
    """Create an NTFS junction directly; no cmd/mklink subprocess or privilege change."""
    import ctypes
    from ctypes import wintypes
    import os
    import struct
    from services.project_retrieval import locked_path
    if os.name != "nt":
        pytest.skip("Physical junction coverage requires Windows/NTFS")
    target = project.root.parent / (project.root.name + "-outside") if outside else project.root / "real"
    target.mkdir()
    (target / "a.py").write_text("value = 1\n")
    link = project.root / "junction"
    link.mkdir()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    control = kernel.DeviceIoControl
    control.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    handle = create(str(link), 0x40000000, 0, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        link.rmdir()
        pytest.skip(f"Cannot open fixture junction for creation: Windows error {ctypes.get_last_error()}")
    try:
        substitute = ("\\??\\" + str(target)).encode("utf-16-le")
        display = str(target).encode("utf-16-le")
        data = struct.pack("<HHHH", 0, len(substitute), len(substitute) + 2, len(display))
        data += substitute + b"\0\0" + display + b"\0\0"
        buffer = ctypes.create_string_buffer(struct.pack("<IHH", 0xA0000003, len(data), 0) + data)
        returned = wintypes.DWORD()
        success = control(handle, 0x900A4, buffer, len(buffer) - 1, None, 0, ctypes.byref(returned), None)
        error = ctypes.get_last_error()
    finally:
        close(handle)
    try:
        if not success:
            pytest.skip(f"Fixture junction creation unsupported or denied: Windows error {error}")
        assert read_source("junction/a.py", project).status == RetrievalStatus.DENIED
        assert discover(project).paths == ([] if outside else ["real/a.py"])
        with pytest.raises(access.ProjectAccessError):
            with locked_path(link / "a.py"):
                pytest.fail("Native handle traversal must reject the actual junction")
    finally:
        # Non-recursive removal unlinks this newly created junction, never target.
        link.rmdir()
