from services.tts import factory


class FakeLocalProvider:
    pass


class FakeElevenLabsProvider:
    def __init__(
        self,
        api_key,
        voice_id,
    ):
        self.api_key = api_key
        self.voice_id = voice_id


def test_factory_creates_local_provider(
    monkeypatch,
):
    monkeypatch.setenv(
        "JARVIS_TTS_PROVIDER",
        "local",
    )

    monkeypatch.setattr(
        factory,
        "LocalTTSProvider",
        FakeLocalProvider,
    )

    provider = factory.create_tts_provider()

    assert isinstance(
        provider,
        FakeLocalProvider,
    )


def test_factory_creates_elevenlabs_provider(
    monkeypatch,
):
    monkeypatch.setenv(
        "JARVIS_TTS_PROVIDER",
        "elevenlabs",
    )
    monkeypatch.setenv(
        "ELEVENLABS_API_KEY",
        "test-key",
    )
    monkeypatch.setenv(
        "ELEVENLABS_VOICE_ID",
        "test-voice",
    )

    monkeypatch.setattr(
        factory,
        "ElevenLabsTTSProvider",
        FakeElevenLabsProvider,
    )

    provider = factory.create_tts_provider()

    assert isinstance(
        provider.primary,
        FakeElevenLabsProvider,
    )
    assert provider.primary.api_key == "test-key"
    assert provider.primary.voice_id == "test-voice"
    assert isinstance(provider.fallback, factory.LocalTTSProvider)


def test_factory_falls_back_when_elevenlabs_fails(
    monkeypatch,
):
    monkeypatch.setenv(
        "JARVIS_TTS_PROVIDER",
        "elevenlabs",
    )

    class FailingElevenLabsProvider:
        def __init__(self, **kwargs):
            raise ValueError("bad configuration")

    monkeypatch.setattr(
        factory,
        "ElevenLabsTTSProvider",
        FailingElevenLabsProvider,
    )
    monkeypatch.setattr(
        factory,
        "LocalTTSProvider",
        FakeLocalProvider,
    )

    provider = factory.create_tts_provider()

    assert isinstance(
        provider,
        FakeLocalProvider,
    )
