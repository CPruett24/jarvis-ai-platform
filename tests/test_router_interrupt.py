from commands import router


def test_streaming_conversation_handles_interrupt(
    monkeypatch,
):

    events = []

    class FakeSpeech:

        def __init__(self):
            self.chunks = []

        def add_chunk(self, text):
            self.chunks.append(text)

        def finish(self):
            events.append(
                ("speech_finish",)
            )
            return []

        def is_finished(self):
            return True

        def wait_until_finished(self):
            return

        def interrupt(self):
            return

    class FakeController:

        def __init__(self, speech):
            self.speech = speech
            self.interrupted = False
            self.text = None

        def handle_speech(self, text):
            self.interrupted = True
            self.text = text

        def was_interrupted(self):
            return self.interrupted

        def get_interrupted_text(self):
            return self.text

    class FakeMonitor:

        def __init__(self, callback):
            self.callback = callback

        def start(self):
            events.append(
                ("monitor_start",)
            )

        def stop(self):
            events.append(
                ("monitor_stop",)
            )

    monkeypatch.setattr(
        router,
        "ConversationSpeech",
        FakeSpeech,
    )

    monkeypatch.setattr(
        router,
        "ConversationInterruptController",
        FakeController,
    )

    monkeypatch.setattr(
        router,
        "SpeechInterruptMonitor",
        FakeMonitor,
    )

    monkeypatch.setattr(
        router,
        "stream_ai_response",
        lambda command: iter(
            [
                "Hello. ",
                "How are you?",
            ]
        ),
    )

    result = (
        router.process_streaming_conversation(
            "hello"
        )
    )

    assert result == (
        "Hello. How are you?"
    )

    assert (
        ("monitor_start",)
        in events
    )

    assert (
        ("monitor_stop",)
        in events
    )

    assert (
        ("speech_finish",)
        in events
    )

def test_streaming_conversation_returns_interruption(
    monkeypatch,
):

    events = []

    class FakeSpeech:

        def __init__(self):
            pass

        def add_chunk(self, text):
            events.append(
                ("speech_chunk", text)
            )

        def finish(self):
            events.append(
                ("speech_finish",)
            )

        def wait_until_finished(self):
            events.append(
                ("speech_wait",)
            )

        def interrupt(self):
            events.append(
                ("speech_interrupt",)
            )

    class FakeController:

        instance = None

        def __init__(self, speech):

            self.speech = speech

            self.interrupted = False
            self.text = None

            FakeController.instance = self

        def handle_speech(self, text):

            self.interrupted = True
            self.text = text

        def was_interrupted(self):
            return self.interrupted

        def get_interrupted_text(self):
            return self.text

    class FakeMonitor:

        def __init__(self, callback):

            self.callback = callback

        def start(self):

            events.append(
                ("monitor_start",)
            )

            FakeController.instance.interrupted = True
            FakeController.instance.text = (
                "wait what about tomorrow"
            )

        def stop(self):

            events.append(
                ("monitor_stop",)
            )

    monkeypatch.setattr(
        router,
        "ConversationSpeech",
        FakeSpeech,
    )

    monkeypatch.setattr(
        router,
        "ConversationInterruptController",
        FakeController,
    )

    monkeypatch.setattr(
        router,
        "SpeechInterruptMonitor",
        FakeMonitor,
    )

    monkeypatch.setattr(
        router,
        "stream_ai_response",
        lambda command: iter(
            [
                "This should not continue."
            ]
        ),
    )

    result = (
        router.process_streaming_conversation(
            "tell me something"
        )
    )

    assert result == (
        router.INTERRUPTION_PREFIX
        + "wait what about tomorrow"
    )

    assert (
        ("monitor_start",)
        in events
    )

    assert (
        ("monitor_stop",)
        in events
    )

    assert (
        ("speech_finish",)
        not in events
    )