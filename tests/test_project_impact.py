from services.project_impact import (
    analyze_function_impact,
    format_function_impact,
)

from services.project_impact import (
    explain_function_impact,
    analyze_file_impact,
    explain_function_impact,
)

from services.project_analysis_index import (
    _normalize_path,
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

def test_explain_function_impact_resolves_execute_tool():

    result = explain_function_impact(
        "what would be affected if I change execute_tool?"
    )

    assert result["status"] == "resolved"

    assert (
        result["target"]["function"]
        == "execute_tool"
    )


def test_explain_function_impact_handles_unknown_target():

    result = explain_function_impact(
        "what would be affected if I change imaginary_function?"
    )

    assert result["status"] == "not_found"

def test_explain_impact_uses_verified_data(monkeypatch):

    from services import ai_service

    captured = {}

    def fake_chat(model, messages):

        captured["model"] = model
        captured["messages"] = messages

        return {
            "message": {
                "content": "Impact explanation."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    impact_data = {
        "target": {
            "file": "commands/tool_manager.py",
            "function": "execute_tool",
        },
        "impact": {
            "callers": [
                {
                    "file": "commands/router.py",
                    "function": "process",
                }
            ]
        },
    }

    response = ai_service.explain_impact(
        "what would be affected if I change execute_tool?",
        impact_data,
    )

    assert response == "Impact explanation."

    assert captured["model"] == "llama3.1:8b"

    prompt = captured["messages"][1]["content"]

    assert "execute_tool" in prompt
    assert "commands/router.py" in prompt
    assert "process" in prompt

def test_analyze_file_impact_finds_router():

    result = analyze_file_impact(
        "router.py"
    )

    assert result is not None

    assert (
        result["target"]["file"]
        .lower()
        .endswith(
            "commands/router.py"
        )
    )

    assert result["functions"]

def test_analyze_file_impact_contains_process():

    result = analyze_file_impact(
        "router.py"
    )

    function_names = [
        item["target"]["function"]
        for item in result["functions"]
    ]

    assert "process" in function_names

def test_analyze_file_impact_finds_router():
    result = analyze_file_impact("router.py")

    assert result is not None
    assert result["target"]["file"].endswith(
        "commands/router.py"
    )


def test_analyze_file_impact_contains_process():
    result = analyze_file_impact("router.py")

    assert result is not None
    assert "process" in result["defined_functions"]


def test_analyze_file_impact_finds_process_callers():
    result = analyze_file_impact("router.py")

    assert result is not None

    assert "process" in result["defined_functions"]

def test_analyze_file_impact_does_not_report_module_as_function():
    result = analyze_file_impact("router.py")

    assert result is not None

    assert "<module>" not in result[
        "defined_functions"
    ]

def test_analyze_file_impact_finds_dependencies():

    result = analyze_file_impact(
        "router.py"
    )

    assert result is not None

    dependencies = result[
        "dependencies"
    ]

    assert any(
        path.endswith(
            "services/intent_resolver.py"
        )
        for path in dependencies
    )


def test_analyze_file_impact_deduplicates_dependencies():

    result = analyze_file_impact(
        "router.py"
    )

    assert result is not None

    dependencies = result[
        "dependencies"
    ]

    assert len(dependencies) == len(
        set(dependencies)
    )