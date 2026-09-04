from commands import router
from models.information import (
    InformationSource,
)
from models.intent import Intent
from services.capability_executor import (
    CapabilityExecutionResult,
    get_observed_information,
)
from services.capability_state import (
    disable_capability,
    enable_capability,
)
from services.capability_service import (
    resolve_capability,
)
from services.conversation_service import (
    clear_history,
    get_conversation_history,
)


def test_static_command_resolves_registered_capability():

    match = resolve_capability(
        "what time is it"
    )

    assert match.source == "static_command"
    assert match.capability_name == "current_time"
    assert match.available is True


def test_disabled_static_capability_is_not_executed(
    monkeypatch,
):

    spoken = []
    executed = []

    monkeypatch.setattr(
        router,
        "speak",
        spoken.append,
    )

    def fake_execute_capability(*args, **kwargs):

        executed.append(args)

        return CapabilityExecutionResult(
            success=False,
            capability="current_time",
            error="Capability is currently disabled.",
        )

    monkeypatch.setattr(
        router,
        "execute_capability",
        fake_execute_capability,
    )

    disable_capability("current_time")

    try:

        router.process("what time is it")

    finally:

        enable_capability("current_time")

    assert executed == [
        ("current_time",)
    ]
    assert "disabled" in spoken[0].lower()


def test_parsed_file_search_uses_capability_execution(
    monkeypatch,
):

    captured = {}
    spoken = []

    def fake_execute_capability(
        capability_name,
        arguments=None,
    ):

        captured["capability_name"] = capability_name
        captured["arguments"] = arguments

        return CapabilityExecutionResult(
            success=True,
            capability=capability_name,
            data={
                "response": "I found 1 matching file.",
                "observations": {
                    "file_search": "router.py",
                    "matches": ["commands/router.py"],
                },
            },
        )

    monkeypatch.setattr(
        router,
        "execute_capability",
        fake_execute_capability,
    )
    monkeypatch.setattr(
        router,
        "speak",
        spoken.append,
    )

    clear_history()

    router.process("find router.py")

    assert captured == {
        "capability_name": "file_search",
        "arguments": {
            "filename": "router.py",
        },
    }
    assert spoken == ["I found 1 matching file."]


def test_successful_capability_execution_records_observations(
    monkeypatch,
):

    monkeypatch.setattr(
        router,
        "speak",
        lambda text: None,
    )
    monkeypatch.setattr(
        router,
        "execute_capability",
        lambda capability_name: CapabilityExecutionResult(
            success=True,
            capability=capability_name,
            data={
                "response": "The current time is 9:00 AM",
                "observations": {
                    "current_time": "9:00 AM",
                },
            },
        ),
    )

    clear_history()

    result = router.execute_registered_capability(
        "current_time"
    )

    assert result.success is True

    history = get_conversation_history()

    assert history == [
        {
            "role": "assistant",
            "content": "[observed] current_time: 9:00 AM",
            "source": "observed",
        }
    ]


def test_failed_capability_execution_records_no_observations(
    monkeypatch,
):

    monkeypatch.setattr(
        router,
        "speak",
        lambda text: None,
    )
    monkeypatch.setattr(
        router,
        "execute_capability",
        lambda capability_name: CapabilityExecutionResult(
            success=False,
            capability=capability_name,
            error="Capability is currently disabled.",
        ),
    )

    clear_history()

    result = router.execute_registered_capability(
        "current_time"
    )

    assert result.success is False
    assert get_conversation_history() == []


def test_structured_observations_are_typed_as_observed_information():

    result = CapabilityExecutionResult(
        success=True,
        capability="current_time",
        data={
            "response": "The current time is 9:00 AM",
            "observations": {
                "current_time": "9:00 AM",
            },
        },
    )

    information = get_observed_information(result)

    assert len(information) == 1
    assert information[0].source == InformationSource.OBSERVED
    assert information[0].content == "current_time: 9:00 AM"


def _route_to_ai_tool_detection(
    monkeypatch,
    selected_tool,
):

    monkeypatch.setattr(
        router,
        "resolve_intent",
        lambda command: Intent(type="other"),
    )
    monkeypatch.setattr(
        router,
        "detect_tool",
        lambda command: selected_tool,
    )


def test_ai_selected_migrated_tool_uses_capability_execution(
    monkeypatch,
):

    spoken = []

    _route_to_ai_tool_detection(
        monkeypatch,
        "current_time",
    )
    monkeypatch.setattr(
        router,
        "speak",
        spoken.append,
    )
    monkeypatch.setattr(
        router,
        "execute_tool",
        lambda request: (_ for _ in ()).throw(
            AssertionError("Migrated tool reached execute_tool")
        ),
    )
    monkeypatch.setattr(
        router,
        "execute_capability",
        lambda capability_name: CapabilityExecutionResult(
            success=True,
            capability=capability_name,
            data={
                "response": "The current time is 9:00 AM",
                "observations": {
                    "current_time": "9:00 AM",
                },
            },
        ),
    )

    clear_history()

    router.process("tell me the time")

    assert spoken == ["The current time is 9:00 AM"]
    assert get_conversation_history() == [
        {
            "role": "assistant",
            "content": "[observed] current_time: 9:00 AM",
            "source": "observed",
        }
    ]


def test_ai_selected_migrated_tool_respects_disabled_state(
    monkeypatch,
):

    spoken = []
    direct_calls = []

    _route_to_ai_tool_detection(
        monkeypatch,
        "current_time",
    )
    monkeypatch.setattr(
        router,
        "speak",
        spoken.append,
    )
    monkeypatch.setattr(
        router,
        "execute_tool",
        direct_calls.append,
    )

    clear_history()
    disable_capability("current_time")

    try:

        router.process("tell me the time")

    finally:

        enable_capability("current_time")

    assert direct_calls == []
    assert "disabled" in spoken[0].lower()
    assert get_conversation_history() == []


def test_ai_selected_unmigrated_tool_uses_existing_execution(
    monkeypatch,
):

    executed = []

    _route_to_ai_tool_detection(
        monkeypatch,
        "hello",
    )
    monkeypatch.setattr(
        router,
        "execute_tool",
        executed.append,
    )

    router.process("say hello")

    assert len(executed) == 1
    assert executed[0].tool == "hello"
    assert executed[0].arguments == {}
