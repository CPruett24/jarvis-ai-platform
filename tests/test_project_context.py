from services.project_context import (
    get_relevant_project_context,
)


def test_roadmap_question_retrieves_multi_file_context():

    context = get_relevant_project_context(
        "What is the next major capability this project is supposed to implement?"
    )

    assert "Multi-File Understanding" in context


def test_architecture_question_retrieves_engineering_principles():

    context = get_relevant_project_context(
        "Would you keep this design based on the project's architecture?"
    )

    assert (
        "Engineering Principles" in context
        or "Core Philosophy" in context
        or "Current Architecture" in context
    )


def test_code_question_retrieves_code_assistant_context():

    context = get_relevant_project_context(
        "How should we improve the code assistant?"
    )

    assert (
        "AI Code Assistant" in context
        or "Developer Assistant" in context
    )


def test_unknown_question_returns_context():

    context = get_relevant_project_context(
        "Tell me something about JARVIS."
    )

    assert context

def test_full_project_context_includes_project_analysis(monkeypatch):

    import services.project_context as project_context

    monkeypatch.setattr(
        project_context,
        "get_project_analysis_index",
        lambda: {
            "files": {
                "router.py": {},
                "main.py": {},
            },
            "symbols": {
                ("router.py", "process"): {},
            },
            "calls": {
                ("router.py", "process"): [],
            },
            "reverse_calls": {},
        },
    )

    monkeypatch.setattr(
        project_context,
        "get_relevant_project_context",
        lambda question: "PROJECT DOCUMENTATION",
    )

    monkeypatch.setattr(
        project_context,
        "get_project_state",
        lambda: {},
    )

    monkeypatch.setattr(
        project_context,
        "format_project_state",
        lambda state: "PROJECT STATE",
    )

    context = project_context.get_full_project_context(
        "what does the project contain?"
    )

    assert "PROJECT DOCUMENTATION" in context
    assert "PROJECT STATE" in context
    assert "router.py" in context
    assert "process" in context

def test_full_project_context_has_analysis_summary(
    monkeypatch,
):

    import services.project_context as project_context

    monkeypatch.setattr(
        project_context,
        "get_project_analysis_index",
        lambda: {
            "files": {
                "router.py": {},
                "main.py": {},
                "services/ai_service.py": {},
            },
            "symbols": {
                ("router.py", "process"): {},
                ("main.py", "<module>"): {},
            },
            "calls": {},
            "reverse_calls": {},
        },
    )

    monkeypatch.setattr(
        project_context,
        "get_relevant_project_context",
        lambda question: "",
    )

    monkeypatch.setattr(
        project_context,
        "get_project_state",
        lambda: {},
    )

    monkeypatch.setattr(
        project_context,
        "format_project_state",
        lambda state: "",
    )

    context = project_context.get_full_project_context(
        "what do you know about this project?"
    )

    assert "PROJECT ANALYSIS" in context
    assert "router.py" in context
    assert "process" in context

def test_get_relevant_project_analysis_includes_function_callers(
    monkeypatch,
):

    import services.project_context as project_context

    monkeypatch.setattr(
        project_context,
        "get_project_analysis_index",
        lambda: {
            "files": {
                "C:/JARVIS/commands/router.py": {},
                "C:/JARVIS/main.py": {},
            },
            "symbols": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): {},
            },
            "calls": {},
            "reverse_calls": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): [
                    {
                        "file": "C:/JARVIS/main.py",
                        "function": "<module>",
                    }
                ]
            },
        },
    )

    context = (
        project_context.get_relevant_project_analysis(
            "what calls process?"
        )
    )

    assert "process" in context
    assert "main.py" in context
    assert "<module>" in context

def test_get_relevant_project_analysis_includes_function_dependencies(
    monkeypatch,
):

    import services.project_context as project_context

    monkeypatch.setattr(
        project_context,
        "get_project_analysis_index",
        lambda: {
            "files": {
                "C:/JARVIS/commands/router.py": {},
            },
            "symbols": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): {},
            },
            "calls": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): [
                    {
                        "call": {
                            "name": "execute_tool",
                            "type": "name",
                        },
                        "target": {
                            "kind": "project_function",
                            "function": "execute_tool",
                            "path": (
                                "C:/JARVIS/commands/"
                                "tool_manager.py"
                            ),
                        },
                    }
                ],
            },
            "reverse_calls": {},
        },
    )

    context = (
        project_context.get_relevant_project_analysis(
            "what does process call?"
        )
    )

    assert "process" in context
    assert "execute_tool" in context
    assert "tool_manager.py" in context

def test_get_relevant_project_analysis_deduplicates_function_calls(
    monkeypatch,
):

    import services.project_context as project_context

    monkeypatch.setattr(
        project_context,
        "get_project_analysis_index",
        lambda: {
            "files": {
                "C:/JARVIS/commands/router.py": {},
            },
            "symbols": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): {},
            },
            "calls": {
                (
                    "C:/JARVIS/commands/router.py",
                    "process",
                ): [
                    {
                        "call": {
                            "name": "execute_tool",
                            "type": "name",
                        },
                        "target": {
                            "kind": "project_function",
                            "function": "execute_tool",
                            "path": (
                                "C:/JARVIS/commands/"
                                "tool_manager.py"
                            ),
                        },
                    },
                    {
                        "call": {
                            "name": "execute_tool",
                            "type": "name",
                        },
                        "target": {
                            "kind": "project_function",
                            "function": "execute_tool",
                            "path": (
                                "C:/JARVIS/commands/"
                                "tool_manager.py"
                            ),
                        },
                    },
                    {
                        "call": {
                            "name": "speak",
                            "type": "name",
                        },
                        "target": {
                            "kind": "project_function",
                            "function": "speak",
                            "path": (
                                "C:/JARVIS/services/"
                                "speaker.py"
                            ),
                        },
                    },
                    {
                        "call": {
                            "name": "speak",
                            "type": "name",
                        },
                        "target": {
                            "kind": "project_function",
                            "function": "speak",
                            "path": (
                                "C:/JARVIS/services/"
                                "speaker.py"
                            ),
                        },
                    },
                ],
            },
            "reverse_calls": {},
        },
    )

    context = (
        project_context.get_relevant_project_analysis(
            "What does process call?"
        )
    )

    assert context.count(
        "tool_manager.py::execute_tool()"
    ) == 1

    assert context.count(
        "speaker.py::speak()"
    ) == 1