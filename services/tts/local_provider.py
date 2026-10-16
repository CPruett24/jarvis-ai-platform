"""Process-isolated native TTS: cancellation never calls SAPI across threads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from services.tts.base import TTSProvider
from services.tts.outcome import PlaybackOutcome
from services.voice_diagnostics import voice_trace


class LocalTTSProvider(TTSProvider):
    # One child at a time, no cancellation threads or pending utterance queue.
    POLL_SECONDS = 0.05
    REAP_SECONDS = 0.5
    MAX_UTTERANCE_SECONDS = 120

    def __init__(self, process_factory=None):
        self.process_factory = process_factory or subprocess.Popen
        self.lock = threading.Lock()
        self.cancelled = None
        self.process = None

    def speak(self, text):
        return self.speak_cancellable(text, threading.Event())

    def speak_cancellable(self, text, cancellation_event):
        if not text:
            return PlaybackOutcome.SKIPPED
        with self.lock:
            if self.cancelled is not None or (self.process is not None and self.process.poll() is None):
                raise RuntimeError("Local TTS is still recovering")
            cancelled = self.cancelled = cancellation_event
        process = None
        try:
            if cancelled.is_set():
                return PlaybackOutcome.INTERRUPTED
            voice_trace("local_start")
            # A file avoids a blocking pipe write when native initialization
            # hangs before reading a large utterance. It is removed on close.
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as payload:
                json.dump(text, payload)
                payload.seek(0)
                process = self.process_factory(
                    [sys.executable, "-m", "services.tts.local_worker"],
                    cwd=str(Path(__file__).resolve().parents[2]),
                    stdin=payload,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
                )
                with self.lock:
                    self.process = process
                deadline = time.monotonic() + self.MAX_UTTERANCE_SECONDS
                while not cancelled.is_set() and time.monotonic() < deadline:
                    try:
                        process.wait(timeout=self.POLL_SECONDS)
                        if process.returncode:
                            raise RuntimeError("Local TTS worker failed")
                        return (PlaybackOutcome.INTERRUPTED if cancelled.is_set()
                                else PlaybackOutcome.COMPLETED)
                    except subprocess.TimeoutExpired:
                        pass
                if not cancelled.is_set():
                    print("[TTS] Local playback timed out.")
                    return PlaybackOutcome.TIMED_OUT
                return PlaybackOutcome.INTERRUPTED
        finally:
            try:
                if process is not None and process.poll() is None:
                    voice_trace("local_terminate")
                    process.terminate()
                    try:
                        process.wait(timeout=self.REAP_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        try:
                            process.wait(timeout=self.REAP_SECONDS)
                        except subprocess.TimeoutExpired:
                            # Keep handle; refuse new children until this one exits.
                            voice_trace("local_recovery_pending")
            finally:
                with self.lock:
                    self.cancelled = None
                voice_trace("local_complete")

    def stop(self):
        voice_trace("local_stop_entry")
        with self.lock:
            if self.cancelled is not None:
                self.cancelled.set()
        voice_trace("local_stop_exit")
