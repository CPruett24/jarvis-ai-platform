import services.ai_service as ai_service


class FakeChunk:

    def __init__(self, text):
        self.data = {
            "message": {
                "content": text
            }
        }

    def __getitem__(self, key):
        return self.data[key]


def test_ask_ai_non_streaming(monkeypatch):

    captured = {}

    def fake_add_message(
        role,
        content,
    ):
        captured.setdefault(
            "messages",
            [],
        ).append(
            (role, content)
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return {
            "message": {
                "content": "Hello from JARVIS."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_context",
        lambda: "No stored memories.",
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "Hello"
    )

    assert result == (
        "Hello from JARVIS."
    )

    assert captured["chat"]["stream"] is False

    assert (
        "user",
        "Hello",
    ) in captured["messages"]

    assert (
        "assistant",
        "Hello from JARVIS.",
    ) in captured["messages"]


def test_ask_ai_streaming(monkeypatch):

    captured = {}

    streamed_chunks = []

    def fake_add_message(
        role,
        content,
    ):
        captured.setdefault(
            "messages",
            [],
        ).append(
            (role, content)
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return iter(
            [
                FakeChunk("Hello "),
                FakeChunk("from "),
                FakeChunk("JARVIS."),
            ]
        )

    def fake_on_chunk(text):

        streamed_chunks.append(
            text
        )

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_context",
        lambda: "No stored memories.",
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "Hello",
        stream=True,
        on_chunk=fake_on_chunk,
    )

    assert result == (
        "Hello from JARVIS."
    )

    assert captured["chat"]["stream"] is True

    assert streamed_chunks == [
        "Hello ",
        "from ",
        "JARVIS.",
    ]

    assert (
        "assistant",
        "Hello from JARVIS.",
    ) in captured["messages"]