from services import conversation_service


def test_restore_recent_history(
    monkeypatch,
):
    conversation_service.clear_history()

    restored_messages = [
        {
            "role": "user",
            "content": "research artificial intelligence trends",
            "timestamp": None,
            "session_id": 1,
            "source": "user",
        },
        {
            "role": "assistant",
            "content": "Research completed.",
            "timestamp": None,
            "session_id": 1,
            "source": "hermes",
        },
    ]

    def fake_get_recent_messages(
        limit,
    ):
        return restored_messages

    monkeypatch.setattr(
        conversation_service,
        "get_recent_messages",
        fake_get_recent_messages,
    )

    conversation_service.restore_recent_history(
        limit=10,
    )

    assert (
        conversation_service.get_conversation_history()
        == [
            {
                "role": "user",
                "content": (
                    "research artificial intelligence trends"
                ),
                "source": "user",
            },
            {
                "role": "assistant",
                "content": "Research completed.",
                "source": "hermes",
            },
        ]
    )

def test_add_message_preserves_source(
    monkeypatch,
):

    conversation_service.clear_history()

    saved = {}

    def fake_save_message(
        role,
        message,
        source=None,
    ):

        saved["role"] = role
        saved["message"] = message
        saved["source"] = source

    monkeypatch.setattr(
        conversation_service,
        "save_message",
        fake_save_message,
    )

    conversation_service.add_message(
        "assistant",
        "Research completed.",
        source="hermes",
    )

    assert (
        conversation_service.get_conversation_history()
        == [
            {
                "role": "assistant",
                "content": "Research completed.",
                "source": "hermes",
            }
        ]
    )

    assert saved == {
        "role": "assistant",
        "message": "Research completed.",
        "source": "hermes",
    }

def test_get_source_aware_history():

    conversation_service.clear_history()

    conversation_service.conversation_history.extend(
        [
            {
                "role": "user",
                "content": (
                    "research artificial intelligence trends"
                ),
                "source": "user",
            },
            {
                "role": "assistant",
                "content": "Research completed.",
                "source": "hermes",
            },
            {
                "role": "assistant",
                "content": "I can explain that further.",
                "source": "ollama",
            },
        ]
    )

    history = (
        conversation_service.get_source_aware_history()
    )

    assert history == [
        {
            "role": "user",
            "content": (
                "research artificial intelligence trends"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Hermes research result:\n"
                "Research completed."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "I can explain that further."
            ),
        },
    ]