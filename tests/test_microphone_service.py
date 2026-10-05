import pytest
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from services import configuration, microphone_service


@pytest.mark.parametrize(
    "preferred,names,expected",
    [
        ("Razer Microphone (Realtek(R) Audio)",
         ["Other", "Razer Microphone (Realtek(R) Audio)"], {"device_index": 1}),
        ("  RAZER microphone  ", ["Other", "Razer Microphone"], {"device_index": 1}),
        ("Razer", ["Other", "Razer", "RAZER"], {"device_index": 1}),
        ("Missing", ["Other"], {}),
        ("Razer", ["Razer Extended"], {}),
        (None, [], {}),
        ("   ", [], {}),
    ],
)
def test_microphone_selection(monkeypatch, capsys, preferred, names, expected):
    monkeypatch.setattr(microphone_service, "load_environment", lambda: None)
    if preferred is None:
        monkeypatch.delenv("JARVIS_MICROPHONE_NAME", raising=False)
    else:
        monkeypatch.setenv("JARVIS_MICROPHONE_NAME", preferred)

    class Microphone:
        def __init__(self, **kwargs):
            self.arguments = kwargs

        @staticmethod
        def list_microphone_names():
            assert preferred and preferred.strip(), "Default must not enumerate devices"
            return names

    monkeypatch.setattr(microphone_service.sr, "Microphone", Microphone)
    assert microphone_service.create_microphone().arguments == expected
    output = capsys.readouterr().out
    if preferred and preferred.strip() and not expected:
        assert "Warning:" in output
        assert "default microphone" in output
    else:
        assert output == ""


def test_environment_loaded_once(monkeypatch):
    calls = []
    configuration.load_environment.cache_clear()
    monkeypatch.setattr(configuration, "load_dotenv", lambda: calls.append(True))
    try:
        configuration.load_environment()
        configuration.load_environment()
        assert calls == [True]
    finally:
        configuration.load_environment.cache_clear()


def test_listener_and_interrupt_monitor_use_shared_selection(monkeypatch):
    microphones = []

    def create():
        microphone = object()
        microphones.append(microphone)
        return microphone

    monkeypatch.setattr(microphone_service, "create_microphone", create)
    monkeypatch.setitem(
        sys.modules, "services.transcription_service",
        SimpleNamespace(transcribe_audio=lambda audio: ""),
    )
    listener = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "services" / "listener.py")
    )
    monitor = listener["SpeechInterruptMonitor"](lambda text: None)
    assert len(microphones) == 2
    assert listener["microphone"] is microphones[0]
    assert monitor.microphone is microphones[1]
