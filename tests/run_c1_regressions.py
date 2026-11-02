"""Strict offline regression entry point; never open production SQLite.

Usage: .venv/Scripts/python tests/run_c1_regressions.py <pytest arguments>
Extends the existing voice harness without weakening its watchdog.
"""
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
import platform
import uuid
import os

REPOSITORY = Path(__file__).resolve().parents[1]
OLLAMA_LOOPBACK = None
ORIGINAL_CONNECT = socket.socket.connect


def forbidden(*args, **kwargs):
    raise AssertionError("C1 guard: network, subprocess, or hardware access denied")


def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1], args[2]
        writing = (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if (path.is_relative_to(REPOSITORY) and not path.is_relative_to(Path(tempfile.gettempdir()))
                and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}):
            raise AssertionError("C1 guard: production SQLite files cannot be opened")
        if writing and (path.is_relative_to(REPOSITORY / "data") or path in {
                REPOSITORY / "AGENTS.md", REPOSITORY / "Codex_Rules.md", REPOSITORY / ".env"}):
            raise AssertionError("C1 guard: production data and local configuration are read-only")
    if event == "sqlite3.connect":
        name = str(args[0])
        if name != ":memory:":
            path = Path(name).resolve()
            if not path.is_relative_to(Path(tempfile.gettempdir()).resolve()):
                raise AssertionError("C1 guard: SQLite must be in memory or temporary storage")
    if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo", "socket.bind"}:
        if OLLAMA_LOOPBACK is None:
            forbidden()
        OLLAMA_LOOPBACK.audit_network(event, args)
    if event in {"subprocess.Popen", "os.system", "os.startfile"}:
        forbidden()


def enable_ollama_loopback(endpoint):
    global OLLAMA_LOOPBACK
    OLLAMA_LOOPBACK = endpoint
    # Both the original runner and this runner block connect during bootstrap.
    # Restoring the method does not remove the process-wide audit admission.
    socket.socket.connect = ORIGINAL_CONNECT


if __name__ == "__main__":
    if "--real-ollama" in sys.argv and "--acceptance" not in sys.argv:
        raise SystemExit("--real-ollama requires --acceptance; regression tests remain offline.")
    # A fresh directory avoids touching existing disposable recall databases
    # and avoids pytest temp ownership differences between Windows tokens.
    sandbox = Path(__file__).resolve().parents[1] / ".c1-test-runs" / uuid.uuid4().hex
    sandbox.mkdir(parents=True)
    tempfile.tempdir = str(sandbox)
    # Python's platform probe can itself spawn cmd.exe. Use host facts directly.
    version = sys.getwindowsversion()
    platform.win32_ver = lambda *a, **k: ("Windows", f"{version.major}.{version.minor}.{version.build}", "", "")
    sys.addaudithook(audit)
    socket.socket.connect = forbidden
    import pytest
    class StrictCollection:
        def pytest_collection_modifyitems(self, items):
            for item in items:
                if item.nodeid.endswith("test_local_cancellation_reaps_blocked_child_and_recovers"):
                    item.add_marker(pytest.mark.skip(reason="C1 guard forbids this legacy test's real child processes"))
    original_main = pytest.main
    def guarded_main(args):
        if "--acceptance" in args:
            if set(args) - {"-p", "no:cacheprovider", "--acceptance", "--interactive", "--real-ollama"}:
                raise SystemExit("Unsupported acceptance arguments.")
            acceptance = runpy.run_path(str(REPOSITORY / "scripts" / "accept_c1.py"))
            return acceptance["main"](interactive="--interactive" in args,
                real_ollama="--real-ollama" in args, enable_loopback=enable_ollama_loopback)
        return original_main(args, plugins=[StrictCollection()])
    pytest.main = guarded_main
    runpy.run_path(str(Path(__file__).with_name("run_voice_regressions.py")), run_name="__main__")
