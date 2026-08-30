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
        },
        {
            "role": "assistant",
            "content": "Research completed.",
            "timestamp": None,
            "session_id": 1,
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
            },
            {
                "role": "assistant",
                "content": "Research completed.",
            },
        ]
    )