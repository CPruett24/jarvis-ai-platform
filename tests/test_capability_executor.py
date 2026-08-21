from services.capability_executor import (
    execute_capability,
)

from services.capability_registry import (
    get_capability,
)


def test_execute_current_time():

    result = execute_capability(
        "current_time"
    )

    assert result.success is True
    assert result.capability == "current_time"
    assert result.error is None


def test_unavailable_calendar():

    result = execute_capability(
        "calendar"
    )

    assert result.success is False
    assert result.capability == "calendar"
    assert result.error is not None

def test_unavailable_calendar():

    result = execute_capability(
        "calendar"
    )

    capability = get_capability(
        "calendar"
    )

    assert result.success is False
    assert result.capability == "calendar"
    assert result.error == capability.reason

def test_unknown_capability():

    result = execute_capability(
        "does_not_exist"
    )

    assert result.success is False
    assert result.capability == "does_not_exist"
    assert result.error == (
        "Capability is not registered."
    )


def test_capability_without_tool():

    result = execute_capability(
        "memory"
    )

    assert result.success is False
    assert result.capability == "memory"
    assert result.error is not None

def test_dict_tool_result_becomes_structured_data(monkeypatch):

    from services import capability_executor

    class FakeTool:

        def __call__(self):
            return {
                "events": [
                    {
                        "title": "Team meeting",
                        "time": "2:00 PM",
                    }
                ],
                "count": 1,
            }

    monkeypatch.setattr(
        capability_executor,
        "get_capability",
        lambda name: type(
            "Capability",
            (),
            {
                "available": True,
                "tool_name": "fake_tool",
                "reason": None,
                "name": "Calendar",
            },
        )(),
    )

    monkeypatch.setattr(
        capability_executor,
        "get_tool",
        lambda name: {
            "function": FakeTool(),
        },
    )

    result = capability_executor.execute_capability(
        "calendar"
    )

    assert result.success is True

    assert result.data == {
        "events": [
            {
                "title": "Team meeting",
                "time": "2:00 PM",
            }
        ],
        "count": 1,
    }


def test_non_dict_tool_result_uses_result_key(monkeypatch):

    from services import capability_executor

    monkeypatch.setattr(
        capability_executor,
        "get_capability",
        lambda name: type(
            "Capability",
            (),
            {
                "available": True,
                "tool_name": "fake_tool",
                "reason": None,
                "name": "Test",
            },
        )(),
    )

    monkeypatch.setattr(
        capability_executor,
        "get_tool",
        lambda name: {
            "function": lambda: "hello world",
        },
    )

    result = capability_executor.execute_capability(
        "test"
    )

    assert result.success is True

    assert result.data == {
        "result": "hello world"
    }

def test_disabled_capability_cannot_execute(monkeypatch):

    from services import capability_executor
    from services.capability_state import (
        disable_capability,
        enable_capability,
    )

    disable_capability(
        "current_time"
    )

    result = capability_executor.execute_capability(
        "current_time"
    )

    assert result.success is False
    assert result.capability == "current_time"
    assert result.error is not None
    assert "disabled" in result.error.lower()

    enable_capability(
        "current_time"
    )


def test_enabled_capability_can_execute(monkeypatch):

    from services import capability_executor
    from services.capability_state import (
        enable_capability,
    )

    enable_capability(
        "current_time"
    )

    result = capability_executor.execute_capability(
        "current_time"
    )

    assert result.success is True