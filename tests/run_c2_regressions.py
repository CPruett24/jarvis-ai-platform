"""Reuse C1 offline guards/voice bootstrap without touching C1 fixture artifacts.

Usage: .venv/Scripts/python -B tests/run_c2_regressions.py <pytest arguments>
Fixtures stay in a fresh OS temporary directory. Tests remain offline; explicit
--acceptance --real-ollama reuses C1's pinned loopback guard for text-only C2 checks.
"""
from pathlib import Path
import platform
import runpy
import socket
import sys
import tempfile

import run_c1_regressions as guards


if __name__ == "__main__":
    if "--real-ollama" in sys.argv and "--acceptance" not in sys.argv:
        raise SystemExit("--real-ollama requires --acceptance; regression tests remain offline.")
    sys.dont_write_bytecode = True
    tempfile.tempdir = tempfile.mkdtemp(prefix="jarvis-c2-")
    version = sys.getwindowsversion()
    platform.win32_ver = lambda *a, **k: ("Windows", f"{version.major}.{version.minor}.{version.build}", "", "")
    sys.addaudithook(guards.audit)
    socket.socket.connect = guards.forbidden
    import pytest

    class StrictCollection:
        def pytest_collection_modifyitems(self, items):
            for item in items:
                if item.nodeid.endswith("test_local_cancellation_reaps_blocked_child_and_recovers"):
                    item.add_marker(pytest.mark.skip(reason="C1 guard forbids this legacy test's real child processes"))

    original_main = pytest.main
    def guarded_main(args):
        if "--acceptance" in args:
            if set(args) - {"-p", "no:cacheprovider", "--acceptance", "--real-ollama"}:
                raise SystemExit("Unsupported C2 acceptance arguments.")
            acceptance = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "accept_c2.py"))
            return acceptance["main"](real_ollama="--real-ollama" in args,
                enable_loopback=guards.enable_ollama_loopback)
        return original_main(args, plugins=[StrictCollection()])
    pytest.main = guarded_main
    runpy.run_path(str(Path(__file__).with_name("run_voice_regressions.py")), run_name="__main__")
