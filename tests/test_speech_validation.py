"""Deterministic control-flow tests; these do not establish acoustic accuracy."""

import ast
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def transcription(monkeypatch):
    model = SimpleNamespace()
    # Avoid model downloads/CUDA initialization while retaining real VAD imports.
    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", lambda *a, **k: model)
    namespace = runpy.run_path(str(ROOT / "services/transcription_service.py"))
    namespace["transcribe_audio"].__globals__["SPEECH_DIAGNOSTICS"] = False
    return namespace, model


@pytest.mark.parametrize("text", ["stop", "wait", "no", "Jarvis", "open the dashboard"])
def test_transcription_enables_vad_and_preserves_text(transcription, text):
    namespace, model = transcription
    paths = []

    def transcribe(path, **options):
        paths.append(path)
        assert Path(path).exists()
        assert options == {"vad_filter": True}
        return iter([SimpleNamespace(text=f" {text} ")]), SimpleNamespace(duration_after_vad=0.2)

    model.transcribe = transcribe
    assert namespace["transcribe_audio"](SimpleNamespace(get_wav_data=lambda: b"wav")) == text
    assert not Path(paths[0]).exists()


def test_zero_retained_speech_never_consumes_decoder(transcription, capsys):
    namespace, model = transcription
    paths = []

    def hallucinated_segments():
        pytest.fail("Zero retained speech must not consume the decoder")
        yield SimpleNamespace(text="hallucination")

    def transcribe(path, **options):
        paths.append(path)
        return hallucinated_segments(), SimpleNamespace(duration=0.5, duration_after_vad=0)

    model.transcribe = transcribe
    namespace["transcribe_audio"].__globals__["SPEECH_DIAGNOSTICS"] = True
    assert namespace["transcribe_audio"](SimpleNamespace(get_wav_data=lambda: b"wav")) == ""
    assert not Path(paths[0]).exists()
    assert "audio=0.50s vad=0.00s segments=0 no_retained_speech=True" in capsys.readouterr().out


def test_decoder_failure_cleans_up(transcription):
    namespace, model = transcription
    paths = []

    def transcribe(path, **options):
        paths.append(path)

        def segments():
            raise RuntimeError("decoder failed")
            yield

        return segments(), SimpleNamespace(duration_after_vad=1)

    model.transcribe = transcribe
    with pytest.raises(RuntimeError, match="decoder failed"):
        namespace["transcribe_audio"](SimpleNamespace(get_wav_data=lambda: b"wav"))
    assert not Path(paths[0]).exists()


def test_segment_diagnostics_are_metadata_only(transcription, capsys):
    namespace, model = transcription
    model.transcribe = lambda *a, **k: (
        iter([SimpleNamespace(text="private utterance", no_speech_prob=0.1,
                              avg_logprob=-0.2, temperature=0)]),
        SimpleNamespace(duration=1.0, duration_after_vad=0.8),
    )
    namespace["transcribe_audio"].__globals__["SPEECH_DIAGNOSTICS"] = True
    assert namespace["transcribe_audio"](SimpleNamespace(get_wav_data=lambda: b"wav")) == "private utterance"
    output = capsys.readouterr().out
    assert "segments=1" in output
    assert "no_speech_prob=0.100 avg_logprob=-0.200 temperature=0" in output
    assert "private utterance" not in output


def test_empty_segment_iterator_returns_empty(transcription):
    namespace, model = transcription
    model.transcribe = lambda *a, **k: (iter([]), SimpleNamespace(duration_after_vad=0.2))
    assert namespace["transcribe_audio"](SimpleNamespace(get_wav_data=lambda: b"wav")) == ""


def test_warmup_preserves_whisper_and_exercises_vad(transcription, monkeypatch):
    namespace, model = transcription
    calls = []
    paths = []

    def transcribe(path, **options):
        paths.append(path)
        assert options == {"language": "en", "beam_size": 1}

        def segments():
            calls.append("whisper")
            yield None

        return segments(), None

    model.transcribe = transcribe
    globals_ = namespace["warm_up_transcription"].__globals__
    monkeypatch.setitem(globals_, "decode_audio", lambda path, **k: "decoded")
    monkeypatch.setitem(globals_, "get_speech_timestamps", lambda audio: calls.append("vad"))
    namespace["warm_up_transcription"]()
    assert calls == ["whisper", "vad"]
    assert not Path(paths[0]).exists()


def test_installed_silero_silence_representation():
    import numpy as np
    from faster_whisper.vad import collect_chunks, get_speech_timestamps

    audio = np.zeros(8000, dtype=np.float32)
    chunks = get_speech_timestamps(audio)
    assert chunks == []
    retained, _ = collect_chunks(audio, chunks)
    assert np.concatenate(retained).size == 0


@pytest.fixture
def listener(monkeypatch):
    from services import microphone_service

    class Microphone:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(microphone_service, "create_microphone", Microphone)
    monkeypatch.setitem(sys.modules, "services.transcription_service", SimpleNamespace(transcribe_audio=lambda a: ""))
    return runpy.run_path(str(ROOT / "services/listener.py"))


@pytest.mark.parametrize("text", ["", "  ", "stop", "wait", "Jarvis", "no"])
def test_interrupt_forwarding(listener, monkeypatch, text):
    callback = []
    monitor = listener["SpeechInterruptMonitor"](callback.append)
    monitor.running = True
    monkeypatch.setitem(monitor._callback.__globals__, "transcribe_audio", lambda a: text)
    monitor._callback(None, object())
    assert callback == ([text] if text.strip() else [])


def test_listener_distinguishes_timeout_from_rejected_capture(listener, monkeypatch):
    import speech_recognition as sr
    audio = SimpleNamespace(frame_data=b"00", sample_rate=16000, sample_width=2)
    recognizer = listener["recognizer"]
    monkeypatch.setattr(recognizer, "listen", lambda *a, **k: audio)
    rejected = listener["listen_for_speech_result"]()
    assert rejected.text == "" and not rejected.timed_out
    assert listener["listen_for_speech"]() == ""

    def timeout(*args, **kwargs):
        raise sr.WaitTimeoutError()

    monkeypatch.setattr(recognizer, "listen", timeout)
    assert listener["listen_for_speech_result"]().timed_out


def test_active_loop_ignores_rejection_then_processes_speech_and_times_out(listener):
    # Execute the actual application loop without startup hardware/DB side effects.
    tree = ast.parse((ROOT / "main.py").read_text())
    loop = next(node for node in tree.body if isinstance(node, ast.While))
    results = iter([
        listener["SpeechListenResult"](),
        listener["SpeechListenResult"](text="open dashboard"),
        listener["SpeechListenResult"](timed_out=True),
    ])
    wakes = iter([True, "exit"])
    spoken, processed, recorded = [], [], []
    context = dict(
        listen_for_wake_word=lambda: next(wakes),
        listen_for_speech_result=lambda: next(results),
        speak=spoken.append, process=processed.append,
        update_last_command=recorded.append, end_session=lambda: None,
        SESSION_END_PHRASES=["thanks"],
    )
    exec(compile(ast.Module(body=[loop], type_ignores=[]), "main.py", "exec"), context)
    assert processed == recorded == ["open dashboard"]
    assert spoken == ["Yes, Chandler?", "Returning to standby.", "Goodbye Chandler."]
