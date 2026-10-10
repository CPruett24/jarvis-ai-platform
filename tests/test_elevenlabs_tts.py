from services.tts.elevenlabs_provider import (
    ElevenLabsTTSProvider,
)


class FakeAudioStream:
    def __init__(self):
        self.writes = []
        self.stopped = False
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def stop_stream(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeAudio:
    def __init__(self):
        self.stream = FakeAudioStream()
        self.open_arguments = None
        self.terminated = False

    def open(self, **kwargs):
        self.open_arguments = kwargs
        return self.stream

    def terminate(self):
        self.terminated = True


class FakeTextToSpeech:
    def __init__(self, chunks):
        self.chunks = chunks
        self.arguments = None

    def stream(self, **kwargs):
        self.arguments = kwargs
        return iter(self.chunks)


class FakeClient:
    def __init__(self, chunks):
        self.text_to_speech = FakeTextToSpeech(
            chunks
        )


def create_provider(chunks=None):
    audio = FakeAudio()
    client = FakeClient(
        chunks
        if chunks is not None
        else [b"first", b"second"]
    )

    provider = ElevenLabsTTSProvider(
        api_key="test-key",
        voice_id="test-voice",
        client=client,
        audio_factory=lambda: audio,
    )

    return provider, client, audio


def test_streams_pcm_audio_to_playback():
    provider, client, audio = create_provider()

    provider.speak("Hello.")

    assert audio.stream.writes == [
        b"first",
        b"second",
    ]

    assert client.text_to_speech.arguments == {
        "voice_id": "test-voice",
        "output_format": "pcm_24000",
        "text": "Hello.",
        "model_id": "eleven_flash_v2_5",
    }

    assert audio.stream.stopped is True
    assert audio.stream.closed is True
    assert audio.terminated is True


def test_empty_text_does_not_open_audio():
    provider, _, audio = create_provider()

    provider.speak("")

    assert audio.open_arguments is None
    assert audio.stream.writes == []


def test_stop_prevents_remaining_audio():
    provider, _, audio = create_provider(
        [b"first", b"second"]
    )

    original_write = audio.stream.write

    def stop_after_first_write(data):
        original_write(data)
        provider.stop()

    audio.stream.write = stop_after_first_write

    provider.speak("Hello.")

    assert audio.stream.writes == [b"first"]
    assert audio.stream.stopped is True


def test_requires_api_key():
    try:
        ElevenLabsTTSProvider(
            api_key=None,
            voice_id="test-voice",
        )
    except ValueError as exc:
        assert "ELEVENLABS_API_KEY" in str(exc)
    else:
        raise AssertionError(
            "Expected missing API key to fail."
        )


def test_requires_voice_id():
    try:
        ElevenLabsTTSProvider(
            api_key="test-key",
            voice_id=None,
        )
    except ValueError as exc:
        assert "ELEVENLABS_VOICE_ID" in str(exc)
    else:
        raise AssertionError(
            "Expected missing voice ID to fail."
        )


def test_lazy_quota_error_cleans_up_audio_and_uses_fallback():
    from types import SimpleNamespace
    from elevenlabs.core.api_error import ApiError
    from services.tts.fallback_provider import FallbackTTSProvider

    primary, client, audio = create_provider()
    calls = []

    def fail_during_iteration(**kwargs):
        calls.append(kwargs["text"])
        raise ApiError(status_code=401, body={"detail": {"status": "quota_exceeded"}})
        yield b"unreachable"

    client.text_to_speech.stream = fail_during_iteration
    spoken = []
    provider = FallbackTTSProvider(primary, SimpleNamespace(speak=spoken.append, stop=lambda: None))
    provider.speak("First.")
    provider.speak("Second.")
    assert calls == ["First."]
    assert spoken == ["First.", "Second."]
    assert audio.stream.closed and audio.terminated
