import pytest

from models.planning_proposal import (
    PlanningProposal,
    TaskProposal,
)

from services.ai_planner import (
    _extract_json,
    _validate_proposal,
    generate_planning_proposal,
)


def test_extract_json_from_plain_json():

    text = """
    {
        "goal_title": "Improve JARVIS",
        "goal_description": "Improve the system.",
        "plan_title": "Improvement Plan",
        "plan_description": "Improve existing capabilities.",
        "tasks": []
    }
    """

    result = _extract_json(text)

    assert result["goal_title"] == (
        "Improve JARVIS"
    )

    assert result["plan_title"] == (
        "Improvement Plan"
    )


def test_extract_json_from_markdown_code_block():

    text = """
    ```json
    {
        "goal_title": "Improve JARVIS",
        "goal_description": "Improve the system.",
        "plan_title": "Improvement Plan",
        "plan_description": "Improve existing capabilities.",
        "tasks": []
    }
    ```
    """

    result = _extract_json(text)

    assert result["goal_title"] == (
        "Improve JARVIS"
    )


def test_extract_json_from_surrounding_text():

    text = """
    Here is the requested plan:

    {
        "goal_title": "Improve JARVIS",
        "goal_description": "Improve the system.",
        "plan_title": "Improvement Plan",
        "plan_description": "Improve existing capabilities.",
        "tasks": []
    }

    That is the plan.
    """

    result = _extract_json(text)

    assert result["goal_title"] == (
        "Improve JARVIS"
    )


def test_validate_proposal():

    data = {
        "goal_title": "Improve conversation",
        "goal_description": "Make JARVIS more natural.",
        "plan_title": "Conversation improvement",
        "plan_description": (
            "Improve conversational behavior."
        ),
        "tasks": [
            {
                "title": "Analyze current behavior",
                "description": "Review existing system.",
                "priority": "high",
                "capability_status": "partial",
                "task_type": "enhancement",
            },
            {
                "title": "Add tests",
                "description": None,
                "priority": "normal",
                "capability_status": "implemented",
                "task_type": "testing",
            },
            {
                "title": "Implement missing capability",
                "description": (
                    "Build the missing capability."
                ),
                "priority": "high",
                "capability_status": "missing",
                "task_type": "implementation",
            },
        ],
    }

    proposal = _validate_proposal(
        data
    )

    assert isinstance(
        proposal,
        PlanningProposal,
    )

    assert proposal.goal_title == (
        "Improve conversation"
    )

    assert len(
        proposal.tasks
    ) == 3

    assert (
        proposal.tasks[0].title
        == "Analyze current behavior"
    )

    assert (
        proposal.tasks[0].capability_status
        == "partial"
    )

    assert (
        proposal.tasks[0].task_type
        == "enhancement"
    )

    assert (
        proposal.tasks[1].capability_status
        == "implemented"
    )

    assert (
        proposal.tasks[1].task_type
        == "testing"
    )

    assert (
        proposal.tasks[2].capability_status
        == "missing"
    )

    assert (
        proposal.tasks[2].task_type
        == "implementation"
    )


def test_validate_proposal_defaults_optional_values():

    data = {
        "goal_title": "Improve conversation",
        "tasks": [
            {
                "title": "Improve conversation",
            }
        ],
    }

    proposal = _validate_proposal(
        data
    )

    assert proposal.goal_title == (
        "Improve conversation"
    )

    assert len(
        proposal.tasks
    ) == 1

    task = proposal.tasks[0]

    assert task.priority == (
        "normal"
    )

    assert task.capability_status == (
        "missing"
    )

    assert task.task_type == (
        "implementation"
    )


def test_validate_rejects_missing_goal_title():

    with pytest.raises(ValueError):

        _validate_proposal(
            {
                "tasks": []
            }
        )


def test_validate_rejects_missing_task_title():

    with pytest.raises(ValueError):

        _validate_proposal(
            {
                "goal_title": "Goal",
                "tasks": [
                    {
                        "description": (
                            "Missing title."
                        ),
                        "priority": "normal",
                        "capability_status": (
                            "missing"
                        ),
                        "task_type": (
                            "implementation"
                        ),
                    }
                ],
            }
        )


def test_validate_rejects_invalid_priority():

    with pytest.raises(ValueError):

        _validate_proposal(
            {
                "goal_title": "Goal",
                "tasks": [
                    {
                        "title": "Task",
                        "priority": "unknown",
                        "capability_status": (
                            "missing"
                        ),
                        "task_type": (
                            "implementation"
                        ),
                    }
                ],
            }
        )


def test_validate_rejects_invalid_capability_status():

    with pytest.raises(ValueError):

        _validate_proposal(
            {
                "goal_title": "Goal",
                "tasks": [
                    {
                        "title": "Task",
                        "priority": "normal",
                        "capability_status": (
                            "unknown"
                        ),
                        "task_type": (
                            "implementation"
                        ),
                    }
                ],
            }
        )


def test_validate_rejects_invalid_task_type():

    with pytest.raises(ValueError):

        _validate_proposal(
            {
                "goal_title": "Goal",
                "tasks": [
                    {
                        "title": "Task",
                        "priority": "normal",
                        "capability_status": (
                            "missing"
                        ),
                        "task_type": (
                            "unknown"
                        ),
                    }
                ],
            }
        )


def test_generate_planning_proposal(
    monkeypatch,
):

    class FakeResponse:

        def __getitem__(
            self,
            key,
        ):

            if key == "message":

                return {
                    "content": """
{
    "goal_title": "Build COO",
    "goal_description": "Build JARVIS COO capabilities.",
    "plan_title": "COO implementation",
    "plan_description": "Build the core COO system.",
    "tasks": [
        {
            "title": "Improve conversation flow",
            "description": "Improve conversational behavior.",
            "priority": "high",
            "capability_status": "partial",
            "task_type": "enhancement"
        },
        {
            "title": "Add conversation tests",
            "description": "Test conversational behavior.",
            "priority": "normal",
            "capability_status": "implemented",
            "task_type": "testing"
        }
    ]
}
"""
                }

            raise KeyError(key)

    captured = {}

    def fake_chat(
        **kwargs,
    ):

        captured["messages"] = (
            kwargs["messages"]
        )

        captured["format"] = (
            kwargs.get("format")
        )

        return FakeResponse()

    monkeypatch.setattr(
        "services.ai_planner.chat",
        fake_chat,
    )

    proposal = generate_planning_proposal(
        "Build the JARVIS COO system."
    )

    assert isinstance(
        proposal,
        PlanningProposal,
    )

    assert proposal.goal_title == (
        "Build COO"
    )

    assert len(
        proposal.tasks
    ) == 2

    assert (
        proposal.tasks[0].title
        == "Improve conversation flow"
    )

    assert (
        proposal.tasks[0]
        .capability_status
        == "partial"
    )

    assert (
        proposal.tasks[0]
        .task_type
        == "enhancement"
    )

    assert (
        proposal.tasks[1].title
        == "Add conversation tests"
    )

    assert (
        proposal.tasks[1]
        .capability_status
        == "implemented"
    )

    assert (
        proposal.tasks[1]
        .task_type
        == "testing"
    )

    assert (
        captured["format"]
        is not None
    )

    assert (
        captured["format"]["type"]
        == "object"
    )

    assert (
        "goal_title"
        in captured["format"]["properties"]
    )

    assert (
        "tasks"
        in captured["format"]["properties"]
    )

    task_properties = (
        captured["format"]
        ["properties"]
        ["tasks"]
        ["items"]
        ["properties"]
    )

    assert (
        "capability_status"
        in task_properties
    )

    assert (
        "task_type"
        in task_properties
    )


def test_generate_planning_proposal_includes_project_context(
    monkeypatch,
):

    captured = {}

    class FakeResponse:

        def __getitem__(
            self,
            key,
        ):

            if key == "message":

                return {
                    "content": """
                    {
                        "goal_title":
                            "Improve JARVIS",
                        "goal_description":
                            "Improve the system.",
                        "plan_title":
                            "Improvement plan",
                        "plan_description":
                            "Improve existing capabilities.",
                        "tasks": [
                            {
                                "title":
                                    "Analyze existing architecture",
                                "description":
                                    "Review current services.",
                                "priority":
                                    "high",
                                "capability_status":
                                    "partial",
                                "task_type":
                                    "enhancement"
                            }
                        ]
                    }
                    """
                }

            raise KeyError(key)

    def fake_documentation(
        question,
    ):

        captured[
            "documentation_question"
        ] = question

        return (
            "===== CURRENT ROADMAP =====\n"
            "Improve conversational intelligence.\n"
        )

    def fake_analysis(
        question,
    ):

        captured[
            "analysis_question"
        ] = question

        return (
            "===== RELEVANT PROJECT ANALYSIS =====\n"
            "conversation_manager.py exists.\n"
            "memory_service.py exists.\n"
        )

    def fake_capabilities():

        captured[
            "capabilities_called"
        ] = True

        return (
            "===== CURRENT JARVIS CAPABILITIES =====\n"
            "Dependency graph construction: implemented.\n"
            "Long-term memory storage: implemented.\n"
            "Agent orchestration: missing.\n"
        )

    def fake_chat(
        **kwargs,
    ):

        captured["messages"] = (
            kwargs["messages"]
        )

        return FakeResponse()

    monkeypatch.setattr(
        "services.ai_planner.get_relevant_project_context",
        fake_documentation,
    )

    monkeypatch.setattr(
        "services.ai_planner.get_relevant_project_analysis",
        fake_analysis,
    )

    monkeypatch.setattr(
        "services.ai_planner.get_project_capabilities",
        fake_capabilities,
    )

    monkeypatch.setattr(
        "services.ai_planner.chat",
        fake_chat,
    )

    proposal = generate_planning_proposal(
        "Improve conversational memory."
    )

    assert proposal.goal_title == (
        "Improve JARVIS"
    )

    assert captured[
        "documentation_question"
    ] == (
        "Improve conversational memory."
    )

    assert captured[
        "analysis_question"
    ] == (
        "Improve conversational memory."
    )

    assert (
        captured["capabilities_called"]
        is True
    )

    user_message = (
        captured["messages"][1]["content"]
    )

    assert (
        "Improve conversational intelligence."
        in user_message
    )

    assert (
        "conversation_manager.py exists."
        in user_message
    )

    assert (
        "memory_service.py exists."
        in user_message
    )

    assert (
        "Dependency graph construction: implemented."
        in user_message
    )

    assert (
        "Long-term memory storage: implemented."
        in user_message
    )

    assert (
        "Agent orchestration: missing."
        in user_message
    )

    assert (
        "Improve conversational memory."
        in user_message
    )


def test_project_capabilities_include_authoritative_statuses():

    from services.project_context import (
        get_project_capabilities,
    )

    capabilities = (
        get_project_capabilities()
    )

    assert (
        "long_term_memory_storage: implemented"
        in capabilities
    )

    assert (
        "memory_search: implemented"
        in capabilities
    )

    assert (
        "autonomous_multi_step_plan_execution: missing"
        in capabilities
    )

def test_validate_capability_statuses_corrects_partial_implementation():

    from services.ai_planner import (
        _validate_capability_statuses,
    )

    proposal = PlanningProposal(
        goal_title="Improve conversation",
        tasks=[
            TaskProposal(
                title=(
                    "Enhance Natural Multi-Turn "
                    "Conversational Reasoning"
                ),
                description=(
                    "Improve natural multi-turn "
                    "conversational reasoning."
                ),
                priority="high",
                capability_status="partial",
                task_type="implementation",
            )
        ],
    )

    result = _validate_capability_statuses(
        proposal
    )

    assert (
        result.tasks[0].capability_status
        == "partial"
    )

    assert (
        result.tasks[0].task_type
        == "enhancement"
    )


def test_filter_out_of_scope_tasks():

    from services.ai_planner import (
        _filter_out_of_scope_tasks,
    )

    proposal = PlanningProposal(
        goal_title="Improve conversation",
        tasks=[
            TaskProposal(
                title=(
                    "Improve conversation memory"
                ),
                description=(
                    "Improve contextual memory."
                ),
                priority="high",
                capability_status="partial",
                task_type="enhancement",
            ),
            TaskProposal(
                title=(
                    "Implement Autonomous "
                    "Multi-Step Plan Execution"
                ),
                description=(
                    "Allow JARVIS to execute "
                    "plans autonomously."
                ),
                priority="critical",
                capability_status="missing",
                task_type="implementation",
            ),
        ],
    )

    result = _filter_out_of_scope_tasks(
        proposal,
        (
            "Improve JARVIS so it can have "
            "natural multi-turn conversations "
            "and remember relevant context."
        ),
    )

    assert len(
        result.tasks
    ) == 1

    assert (
        "conversation"
        in result.tasks[0].title.lower()
    )