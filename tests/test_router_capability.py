from commands import router


def test_unavailable_high_level_capability_is_handled(
    monkeypatch,
):
    spoken = []
    ai_called = []

    def fake_speak(text):
        spoken.append(text)

    def fake_ask_ai(command):
        ai_called.append(command)
        return "AI response"

    monkeypatch.setattr(
        router,
        "speak",
        fake_speak,
    )

    monkeypatch.setattr(
        router,
        "ask_ai",
        fake_ask_ai,
    )

    router.process(
        "what's on my calendar"
    )

    assert ai_called == []

    assert len(spoken) == 1

    assert (
        "calendar"
        in spoken[0].lower()
    )

    assert (
        "not"
        in spoken[0].lower()
        or "can't"
        in spoken[0].lower()
        or "cannot"
        in spoken[0].lower()
    )


def test_available_high_level_capability_is_executed(
    monkeypatch,
):
    executed = []
    spoken = []

    class FakeResult:
        success = True
        message = "Calendar capability executed."
        error = None
        data = {}

    def fake_execute_capability(
        capability_name,
    ):
        executed.append(
            capability_name
        )

        return FakeResult()

    def fake_speak(text):
        spoken.append(text)

    monkeypatch.setattr(
        router,
        "is_capability_available",
        lambda capability_name: True,
    )

    monkeypatch.setattr(
        router,
        "execute_capability",
        fake_execute_capability,
    )

    monkeypatch.setattr(
        router,
        "speak",
        fake_speak,
    )

    router.process(
        "what's on my calendar"
    )

    assert executed == [
        "calendar"
    ]

    assert spoken == [
        "Calendar capability executed."
    ]

def test_normal_conversation_does_not_trigger_capability(
    monkeypatch,
):
    executed = []
    streamed = []

    def fake_execute_capability(
        capability_name,
    ):
        executed.append(
            capability_name
        )

        return None

    def fake_streaming_conversation(
        command,
    ):
        streamed.append(command)
        return "conversation response"

    monkeypatch.setattr(
        router,
        "execute_capability",
        fake_execute_capability,
    )

    monkeypatch.setattr(
        router,
        "process_streaming_conversation",
        fake_streaming_conversation,
    )

    router.process(
        "tell me about my project"
    )

    assert executed == []

    assert streamed == [
        "tell me about my project"
    ]


def test_incidental_capability_language_does_not_trigger_capability(
    monkeypatch,
):
    executed = []
    streamed = []

    def fake_execute_capability(
        capability_name,
    ):
        executed.append(
            capability_name
        )

        return None

    def fake_streaming_conversation(
        command,
    ):
        streamed.append(command)
        return "conversation response"

    monkeypatch.setattr(
        router,
        "execute_capability",
        fake_execute_capability,
    )

    monkeypatch.setattr(
        router,
        "process_streaming_conversation",
        fake_streaming_conversation,
    )

    router.process(
        "tell me about organizing my day"
    )

    assert executed == []

    assert streamed == [
        "tell me about organizing my day"
    ]

def test_disabled_capability_is_not_executed(monkeypatch):

    from commands import router
    from services.capability_state import (
        disable_capability,
        enable_capability,
    )

    executed = []

    monkeypatch.setattr(
        router,
        "execute_capability",
        lambda name: (
            executed.append(name)
            or type(
                "Result",
                (),
                {
                    "success": True,
                    "message": "should not execute",
                    "error": None,
                },
            )()
        ),
    )

    disable_capability(
        "calendar"
    )

    try:

        router.process(
            "what's on my calendar"
        )

        assert executed == []

    finally:

        enable_capability(
            "calendar"
        )