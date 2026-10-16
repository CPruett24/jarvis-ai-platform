"""Run selected voice tests without hardware, network, or production storage.

Usage: .venv/Scripts/python tests/run_voice_regressions.py <pytest arguments>
An overall watchdog exits after 120 seconds, printing thread stacks first.
"""
import faulthandler
import os
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["JARVIS_TTS_PROVIDER"] = "local"


def forbidden(*args, **kwargs):
    raise AssertionError("External network access is forbidden in voice regressions")


def watchdog():
    faulthandler.dump_traceback(all_threads=True)
    os._exit(124)


if __name__ == "__main__":
    socket.socket.connect = forbidden
    import sqlalchemy
    from sqlalchemy.pool import StaticPool

    original_create = sqlalchemy.create_engine

    def isolated_engine(url, *args, **kwargs):
        if str(url) == "sqlite:///data/jarvis.db":
            return original_create("sqlite://", poolclass=StaticPool,
                                   connect_args={"check_same_thread": False})
        return original_create(url, *args, **kwargs)

    sqlalchemy.create_engine = isolated_engine
    import speech_recognition as sr

    class Microphone:
        def __init__(self, **kwargs):
            pass

        @staticmethod
        def list_microphone_names():
            return [os.getenv("JARVIS_MICROPHONE_NAME", "Test microphone")]

    sr.Microphone = Microphone
    import faster_whisper
    original_model = faster_whisper.WhisperModel
    faster_whisper.WhisperModel = lambda *a, **k: SimpleNamespace(transcribe=forbidden)
    import services.transcription_service
    faster_whisper.WhisperModel = original_model
    from services import status_service
    status_service.update_status = lambda *a, **k: None
    status_service.update_last_response = lambda *a, **k: None
    status_service.update_last_command = lambda *a, **k: None
    from commands import router
    from services import speaker
    speaker._default_speaker.provider.speak = forbidden
    speaker._default_speaker.provider.stop = lambda: None
    from models.database import Base, engine
    Base.metadata.create_all(engine)

    timer = threading.Timer(120, watchdog)
    timer.daemon = True
    timer.start()
    import pytest
    try:
        raise SystemExit(pytest.main(["-p", "no:cacheprovider", *sys.argv[1:]]))
    finally:
        timer.cancel()
