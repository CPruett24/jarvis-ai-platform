from services.project_execution import (
    get_function_calls,
    trace_execution,
    format_execution_trace,
    resolve_registered_tool,
    trace_tool_execution,
    format_tool_execution_trace,
)


def test_router_process_function_exists():

    result = get_function_calls(
        "router.py",
        "process",
    )

    assert result is not None
    assert result["function"] == "process"


def test_router_process_resolves_intent():

    result = get_function_calls(
        "router.py",
        "process",
    )

    assert result is not None

    resolved_functions = [
        item["target"]["function"]
        for item in result["resolved_calls"]
        if item["target"].get("function")
    ]

    assert "resolve_intent" in resolved_functions


def test_router_process_resolves_tool_manager():

    result = get_function_calls(
        "router.py",
        "process",
    )

    assert result is not None

    resolved_modules = [
        item["target"].get("module")
        for item in result["resolved_calls"]
    ]

    assert (
        "commands.tool_manager"
        in resolved_modules
    )


def test_execution_trace_contains_router():

    trace = trace_execution(
        "router.py",
        "process",
    )

    assert trace is not None

    assert trace["function"] == "process"


def test_execution_trace_reaches_project_functions():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=3,
    )

    formatted = format_execution_trace(
        trace
    )

    assert "router.py::process()" in formatted

    assert (
        "intent_resolver.py::resolve_intent()"
        in formatted
    )


def test_execution_trace_can_be_formatted():

    trace = trace_execution(
        "router.py",
        "process",
    )

    formatted = format_execution_trace(
        trace
    )

    assert formatted is not None
    assert len(formatted) > 0


def test_unknown_function_returns_none():

    result = get_function_calls(
        "router.py",
        "does_not_exist",
    )

    assert result is None


def test_unknown_file_returns_none():

    result = trace_execution(
        "does_not_exist.py",
        "process",
    )

    assert result is None

def test_registered_tool_resolves():

    result = resolve_registered_tool(
        "open_github"
    )

    assert result is not None

    assert result["tool"] == "open_github"

    assert result["function"] == "open_github"

    assert result["module"] == "commands.actions"

    assert result["path"].endswith(
        "commands/actions.py"
    )


def test_unknown_registered_tool_returns_none():

    result = resolve_registered_tool(
        "does_not_exist"
    )

    assert result is None


def test_tool_execution_trace():

    result = trace_tool_execution(
        "open_github"
    )

    assert result is not None

    assert result["tool"] == "open_github"

    assert result["function"] == "open_github"

    assert result["module"] == "commands.actions"

    assert result["trace"] is not None


def test_tool_execution_trace_contains_function():

    result = trace_tool_execution(
        "open_github"
    )

    formatted = format_tool_execution_trace(
        result
    )

    assert formatted is not None

    assert (
        "commands.actions.open_github()"
        in formatted
    )


def test_unknown_tool_execution_returns_none():

    result = trace_tool_execution(
        "does_not_exist"
    )

    assert result is None

def test_builtin_calls_are_classified():

    result = get_function_calls(
        "router.py",
        "process",
    )

    assert result is not None

    builtin_calls = [
        call
        for call in result["unresolved_calls"]
        if call["type"] == "builtin"
    ]

    assert any(
        call["name"] == "print"
        for call in builtin_calls
    )


def test_attribute_calls_are_classified():

    result = get_function_calls(
        "router.py",
        "process",
    )

    assert result is not None

    attribute_calls = [
        call
        for call in result["unresolved_calls"]
        if call["type"] == "external_or_runtime"
    ]

    assert any(
        call["name"] in {
            "lower",
            "strip",
            "get",
            "split",
        }
        for call in attribute_calls
    )


def test_dynamic_calls_are_classified():

    result = get_function_calls(
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    dynamic_calls = [
        call
        for call in result["unresolved_calls"]
        if call["type"] == "dynamic"
    ]

    assert any(
        "function" in call["name"]
        for call in dynamic_calls
    )


def test_execution_trace_marks_project_functions():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=2,
    )

    assert trace is not None

    assert trace["category"] == "project"


def test_formatted_trace_contains_categories():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=2,
    )

    formatted = format_execution_trace(
        trace
    )

    assert "[PROJECT]" in formatted
    assert "[BUILTIN]" in formatted