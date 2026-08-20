from commands.router import (
    process_streaming_conversation,
)


def test_process_streaming_conversation(
    monkeypatch,
):

    chunks = [
        "Hello ",
        "from ",
        "JARVIS. ",
        "How ",
        "are ",
        "you?",
    ]

    spoken = []

    def fake_stream_ai_response(
        command,
    ):

        assert command == (
            "How are you?"
        )

        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(
        "commands.router.stream_ai_response",
        fake_stream_ai_response,
    )

    class FakeConversationSpeech:

        def __init__(self):

            self.chunks = []

        def add_chunk(self, text):

            self.chunks.append(text)

        def finish(self):

            return []

        def is_finished(self):

            return True

        def wait_until_finished(self):

            return

        def stop(self):

            return

    monkeypatch.setattr(
        "commands.router.ConversationSpeech",
        FakeConversationSpeech,
    )

    result = process_streaming_conversation(
        "How are you?"
    )

    assert result == (
        "Hello from JARVIS. "
        "How are you?"
    )

def test_process_routes_conversation_to_streaming(
    monkeypatch,
):

    called = {}

    def fake_streaming_conversation(
        command,
    ):

        called["command"] = command

    class FakeIntent:

        type = "conversation"
        confidence = 1.0

    monkeypatch.setattr(
        "commands.router.resolve_intent",
        lambda command: FakeIntent(),
    )

    monkeypatch.setattr(
        "commands.router.process_streaming_conversation",
        fake_streaming_conversation,
    )

    process = __import__(
        "commands.router",
        fromlist=["process"],
    ).process

    process(
        "How are you?"
    )

    assert called["command"] == (
        "how are you"
    )