import services.ai_service as ai_service

from models.information import (
    InformationSource,
)

from services.grounding_service import (
    create_information_item,
)


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

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
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
        "get_memory_information",
        lambda: [
            create_information_item(
                "Your project deadline is Friday.",
                InformationSource.REMEMBERED,
            )
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
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
        "[remembered] "
        "Your project deadline is Friday."
        in captured["chat"]["messages"][0]["content"]
    )

    assert saved_messages == [
        {
            "role": "user",
            "message": "Hello",
            "source": "user",
        },
        {
            "role": "assistant",
            "message": "Hello from JARVIS.",
            "source": "ollama",
        },
    ]

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": "Hello",
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "Hello from JARVIS.",
                "source": "ollama",
            },
        ]
    )


def test_ask_ai_streaming(monkeypatch):

    captured = {}

    streamed_chunks = []

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
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
        "get_memory_information",
        lambda: [
            create_information_item(
                "Your project deadline is Friday.",
                InformationSource.REMEMBERED,
            )
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
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

    assert (
        "[remembered] "
        "Your project deadline is Friday."
        in captured["chat"]["messages"][0]["content"]
    )

    assert streamed_chunks == [
        "Hello ",
        "from ",
        "JARVIS.",
    ]

    assert saved_messages == [
        {
            "role": "user",
            "message": "Hello",
            "source": "user",
        },
        {
            "role": "assistant",
            "message": "Hello from JARVIS.",
            "source": "ollama",
        },
    ]

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": "Hello",
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "Hello from JARVIS.",
                "source": "ollama",
            },
        ]
    )