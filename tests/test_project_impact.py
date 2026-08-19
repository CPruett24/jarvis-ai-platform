from services.project_impact import (
    analyze_function_impact,
    format_function_impact,
)


def test_execute_tool_has_router_caller():

    result = analyze_function_impact(
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    callers = result["impact"]["callers"]

    assert any(
        caller["function"] == "process"
        and caller["file"].endswith(
            "commands/router.py"
        )
        for caller in callers
    )


def test_impact_contains_target():

    result = analyze_function_impact(
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    assert (
        result["target"]["function"]
        == "execute_tool"
    )


def test_unknown_function_returns_none():

    result = analyze_function_impact(
        "tool_manager.py",
        "does_not_exist",
    )

    assert result is None


def test_impact_can_be_formatted():

    result = analyze_function_impact(
        "tool_manager.py",
        "execute_tool",
    )

    formatted = format_function_impact(
        result
    )

    assert "execute_tool" in formatted
    assert "router.py" in formatted
    assert "process" in formatted