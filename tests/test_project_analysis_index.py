from services.project_analysis_index import (
    build_project_analysis_index,
    find_indexed_function_callers,
)


def test_index_contains_router_process():

    index = build_project_analysis_index()

    matches = [
        key
        for key in index["symbols"]
        if key[1] == "process"
        and key[0].endswith(
            "commands/router.py"
        )
    ]

    assert matches


def test_index_contains_execute_tool():

    index = build_project_analysis_index()

    matches = [
        key
        for key in index["symbols"]
        if key[1] == "execute_tool"
        and key[0].endswith(
            "commands/tool_manager.py"
        )
    ]

    assert matches


def test_index_finds_execute_tool_callers():

    index = build_project_analysis_index()

    result = find_indexed_function_callers(
        index,
        "tool_manager.py",
        "execute_tool",
    )

    assert result is not None

    callers = result["callers"]

    assert any(
        caller["function"] == "process"
        and caller["file"].endswith(
            "commands/router.py"
        )
        for caller in callers
    )


def test_index_does_not_guess_dynamic_calls():

    index = build_project_analysis_index()

    result = find_indexed_function_callers(
        index,
        "speaker.py",
        "speak",
    )

    assert result is not None

def test_project_analysis_index_is_cached():

    from services.project_analysis_index import (
        get_project_analysis_index,
        clear_project_analysis_index_cache,
        get_project_analysis_index_cache_info,
    )

    clear_project_analysis_index_cache()

    get_project_analysis_index()

    first = (
        get_project_analysis_index_cache_info()
    )

    get_project_analysis_index()

    second = (
        get_project_analysis_index_cache_info()
    )

    assert second.hits == first.hits + 1