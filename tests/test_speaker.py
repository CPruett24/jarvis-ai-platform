from services.speaker import InterruptibleSpeaker


class FakeTTSProvider:
    def __init__(self):
        self.spoken = []
        self.stop_called = False

    def speak(self, text):
        self.spoken.append(text)

    def stop(self):
        self.stop_called = True


def test_speaker_delegates_speech_to_provider(
    monkeypatch,
):
    provider = FakeTTSProvider()

    monkeypatch.setattr(
        "services.speaker.update_status",
        lambda status: None,
    )
    monkeypatch.setattr(
        "services.speaker.update_last_response",
        lambda response: None,
    )

    speaker = InterruptibleSpeaker(
        provider=provider,
    )

    speaker.speak("Hello.")

    assert provider.spoken == ["Hello."]
    assert speaker.is_speaking() is False


def test_speaker_stop_delegates_to_provider(
    monkeypatch,
):
    provider = FakeTTSProvider()

    monkeypatch.setattr(
        "services.speaker.update_status",
        lambda status: None,
    )
    monkeypatch.setattr(
        "services.speaker.update_last_response",
        lambda response: None,
    )

    speaker = InterruptibleSpeaker(
        provider=provider,
    )

    speaker.stop()

    assert provider.stop_called is True
    assert speaker.is_speaking() is False


def test_empty_speech_does_not_call_provider(
    monkeypatch,
):
    provider = FakeTTSProvider()

    monkeypatch.setattr(
        "services.speaker.update_status",
        lambda status: None,
    )
    monkeypatch.setattr(
        "services.speaker.update_last_response",
        lambda response: None,
    )

    speaker = InterruptibleSpeaker(
        provider=provider,
    )

    speaker.speak("")

    assert provider.spoken == []