import threading

import pytest
from elevenlabs.core.api_error import ApiError

from services.tts.fallback_provider import FallbackTTSProvider
from services.conversation_speech import ConversationSpeech
from services.speaker import InterruptibleSpeaker


class Provider:
    def __init__(self, error=None):
        self.error = error
        self.spoken = []
        self.stops = 0

    def speak(self, text):
        self.spoken.append(text)
        if self.error:
            raise self.error

    def stop(self):
        self.stops += 1


def quota_error(body=None):
    return ApiError(status_code=401, headers={"secret": "credential-sentinel"},
                    body=body or {"detail": {"status": "quota_exceeded", "message": "0 credits left; 121 required"}})


def test_success_keeps_primary_voice():
    primary, local = Provider(), Provider()
    provider = FallbackTTSProvider(primary, local)
    provider.speak("Hello.")
    assert primary.spoken == ["Hello."]
    assert local.spoken == []
    assert not provider.quota_exhausted


@pytest.mark.parametrize("body", [
    {"detail": {"status": "quota_exceeded"}},
    {"detail": {"code": "quota_exceeded"}},
    {"code": "quota_exceeded"},
])
def test_quota_latches_fallback_and_logs_no_credentials(body, capsys):
    primary, local = Provider(quota_error(body)), Provider()
    provider = FallbackTTSProvider(primary, local)
    provider.speak("First.")
    provider.speak("Second.")
    assert primary.spoken == ["First."]
    assert local.spoken == ["First.", "Second."]
    assert provider.quota_exhausted
    output = capsys.readouterr().out
    assert output.count("quota exceeded") == 1
    assert "credential-sentinel" not in output
    assert "headers" not in output


@pytest.mark.parametrize("error", [ConnectionError("credential-sentinel"),
    ApiError(status_code=503, body={"detail": {"status": "unavailable"}}),
    ApiError(status_code=401, body={"detail": {"status": "invalid_api_key"}})])
def test_temporary_or_nonquota_error_falls_back_without_latching(error, capsys):
    primary, local = Provider(error), Provider()
    provider = FallbackTTSProvider(primary, local)
    provider.speak("First.")
    primary.error = None
    provider.speak("Second.")
    assert primary.spoken == ["First.", "Second."]
    assert local.spoken == ["First."]
    assert not provider.quota_exhausted
    assert "credential-sentinel" not in capsys.readouterr().out


def test_fallback_failure_is_contained_and_future_utterances_recover(capsys):
    primary, local = Provider(quota_error()), Provider(RuntimeError("credential-sentinel"))
    provider = FallbackTTSProvider(primary, local)
    provider.speak("First.")
    local.error = None
    provider.speak("Second.")
    assert primary.spoken == ["First."]
    assert local.spoken == ["First.", "Second."]
    output = capsys.readouterr().out
    assert "Local speech failed (RuntimeError)" in output
    assert "credential-sentinel" not in output


def test_new_provider_lifetime_can_retry_after_quota():
    primary = Provider(quota_error())
    FallbackTTSProvider(primary, Provider()).speak("First.")
    primary.error = None
    FallbackTTSProvider(primary, Provider()).speak("Next run.")
    assert primary.spoken == ["First.", "Next run."]


@pytest.mark.parametrize("stage", ["primary", "local"])
def test_stop_during_failure_does_not_start_fallback_or_remaining_speech(stage):
    started, released = threading.Event(), threading.Event()

    class Blocking(Provider):
        def speak(self, text):
            self.spoken.append(text)
            started.set()
            assert released.wait(2)
            raise quota_error()

        def stop(self):
            super().stop()
            released.set()

    primary = Blocking() if stage == "primary" else Provider(quota_error())
    local = Blocking() if stage == "local" else Provider()
    provider = FallbackTTSProvider(primary, local)
    worker = threading.Thread(target=provider.speak, args=("Interrupted.",))
    worker.start()
    try:
        assert started.wait(2)
        provider.stop()
    finally:
        released.set()
        worker.join(2)
    assert not worker.is_alive()
    assert (primary if stage == "primary" else local).stops == 1
    if stage == "primary":
        assert local.spoken == []


def test_worker_survives_failed_sentence_and_preserves_order(capsys):
    spoken, done = [], threading.Event()

    def speak(text):
        spoken.append(text)
        if len(spoken) == 1:
            raise RuntimeError("credential-sentinel")
        done.set()

    speech = ConversationSpeech(speak_function=speak, stop_function=lambda: None)
    try:
        speech.add_chunk("First sentence. Second sentence.")
        speech.finish()
        assert done.wait(2)
        speech.speech_queue.join()
        assert speech.worker.is_alive()
        assert speech.is_finished()
        assert spoken == ["First sentence.", "Second sentence."]
        output = capsys.readouterr().out
        assert "Speech worker failed (RuntimeError)" in output
        assert "credential-sentinel" not in output
    finally:
        speech.stop()
        speech.worker.join(2)


def test_speaker_contains_local_provider_failure(monkeypatch, capsys):
    monkeypatch.setattr("services.speaker.update_status", lambda *a: None)
    monkeypatch.setattr("services.speaker.update_last_response", lambda *a: None)
    speaker = InterruptibleSpeaker(Provider(RuntimeError("credential-sentinel")))
    speaker.speak("Hello.")
    assert not speaker.is_speaking()
    assert "Speech failed (RuntimeError)" in capsys.readouterr().out


def test_streamed_sentences_continue_in_order_after_quota(monkeypatch):
    monkeypatch.setattr("services.speaker.update_status", lambda *a: None)
    monkeypatch.setattr("services.speaker.update_last_response", lambda *a: None)
    primary, local = Provider(quota_error()), Provider()
    speaker = InterruptibleSpeaker(FallbackTTSProvider(primary, local))
    speech = ConversationSpeech(speak_function=speaker.speak, stop_function=speaker.stop)
    try:
        speech.add_chunk("First sentence. Second sentence.")
        speech.finish()
        speech.speech_queue.join()
        assert primary.spoken == ["First sentence."]
        assert local.spoken == ["First sentence.", "Second sentence."]
        assert speech.worker.is_alive() and speech.is_finished()
    finally:
        speech.stop()
        speech.worker.join(2)
