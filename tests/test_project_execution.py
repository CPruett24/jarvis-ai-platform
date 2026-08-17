from services.project_execution import (
    get_function_calls,
    trace_execution,
    format_execution_trace,
    resolve_registered_tool,
    trace_tool_execution,
    format_tool_execution_trace,
)

from services.project_analysis_cache import (
    clear_analysis_cache,
    get_analysis_cache_info,
)

from services.project_symbol_index import (
    find_function,
    find_class,
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
    assert "[PYTHON_BUILTIN]" in formatted

def test_standard_library_import_is_detected():

    from pathlib import Path

    project_file = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "project_service.py"
    )

    from services.project_execution import (
        _get_imported_modules,
    )

    imported_modules = _get_imported_modules(
        project_file
    )

    assert imported_modules.get(
        "Path"
    ) == "pathlib"


def test_third_party_import_is_classified():

    result = get_function_calls(
        "ai_service.py",
        "ask_ai",
    )

    assert result is not None

    third_party_calls = [
        call
        for call in result["unresolved_calls"]
        if call["type"] == "third_party"
    ]

    assert any(
        call["module"] == "ollama"
        for call in third_party_calls
    )


def test_builtin_classification_still_works():

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

def test_analysis_cache_reuses_source_tree():
    clear_analysis_cache()

    trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    first = get_analysis_cache_info()

    trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    second = get_analysis_cache_info()

    assert second["source_tree"].hits > first["source_tree"].hits


def test_analysis_cache_invalidates_when_file_changes():
    clear_analysis_cache()

    trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    first = get_analysis_cache_info()

    trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    second = get_analysis_cache_info()

    assert second["source_tree"].hits > first["source_tree"].hits

def test_find_function_callers_finds_execute_tool():

    from services.project_execution import (
        find_function_callers,
    )

    result = find_function_callers(
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    callers = result["callers"]

    router_callers = [
        caller
        for caller in callers
        if caller["file"].endswith(
            "commands/router.py"
        )
        and caller["function"] == "process"
    ]

    assert len(router_callers) == 1


def test_find_function_callers_returns_target():

    from services.project_execution import (
        find_function_callers,
    )

    result = find_function_callers(
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    assert result["function"] == (
        "execute_tool"
    )

    assert result["file"].endswith(
        "commands/tool_manager.py"
    )


def test_find_function_callers_does_not_guess_dynamic_calls():

    from services.project_execution import (
        find_function_callers,
    )

    result = find_function_callers(
        "speaker.py",
        "speak",
    )

    assert result is not None

    for caller in result["callers"]:

        assert caller["function"]
        assert caller["file"]

def test_symbol_index_contains_functions():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    assert trace is not None

    symbol_index = trace["symbol_index"]

    assert any(
        function["name"] == "process"
        for function in symbol_index["functions"]
    )


def test_symbol_index_contains_imports():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    assert trace is not None

    symbol_index = trace[
        "symbol_index"
    ]

    ask_ai_import = next(
        (
            item
            for item in symbol_index[
                "imports"
            ]
            if item["name"] == "ask_ai"
        ),
        None,
    )

    assert ask_ai_import is not None

    assert ask_ai_import[
        "module"
    ] == "services.ai_service"


def test_find_function():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    assert trace is not None

    result = find_function(
        trace["symbol_index"],
        "process",
    )

    assert result is not None
    assert result["name"] == "process"


def test_find_class():

    trace = trace_execution(
        "router.py",
        "process",
        max_depth=1,
    )

    assert trace is not None

    result = find_class(
        trace["symbol_index"],
        "SomeClassThatDoesNotExist",
    )

    assert result is None