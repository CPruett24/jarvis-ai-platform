import pytest

from models.database import (
    Base,
    engine,
    SessionLocal,
)

from models.goal import Goal
from models.plan import Plan
from models.task import Task

from services.planning_engine import (
    create_plan_from_tasks,
)

from models.planning_proposal import (
    PlanningProposal,
    TaskProposal,
)

from services.planning_engine import (
    persist_planning_proposal,
)


@pytest.fixture(autouse=True)
def clean_planning_data():

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:
        db.query(Task).delete()
        db.query(Plan).delete()
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()

    yield

    db = SessionLocal()

    try:
        db.query(Task).delete()
        db.query(Plan).delete()
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()


def test_create_plan_from_tasks():

    result = create_plan_from_tasks(
        goal_title="Improve JARVIS conversation",
        goal_description=(
            "Make JARVIS better at natural multi-turn "
            "conversation."
        ),
        plan_title="Improve conversational intelligence",
        plan_description=(
            "Analyze and improve conversation handling."
        ),
        tasks=[
            {
                "title": "Analyze conversation manager",
                "description": (
                    "Review current conversation state handling."
                ),
                "priority": "high",
            },
            {
                "title": "Improve context handling",
                "description": (
                    "Improve how relevant context is retained."
                ),
                "priority": "high",
            },
            {
                "title": "Add conversational tests",
                "priority": "normal",
            },
        ],
    )

    goal = result["goal"]
    plan = result["plan"]
    tasks = result["tasks"]

    assert goal.id is not None
    assert goal.title == "Improve JARVIS conversation"

    assert plan.id is not None
    assert plan.goal_id == goal.id
    assert (
        plan.title
        == "Improve conversational intelligence"
    )

    assert len(tasks) == 3

    assert tasks[0].title == (
        "Analyze conversation manager"
    )

    assert tasks[1].title == (
        "Improve context handling"
    )

    assert tasks[2].title == (
        "Add conversational tests"
    )

    assert tasks[0].goal_id == goal.id
    assert tasks[1].goal_id == goal.id
    assert tasks[2].goal_id == goal.id

    assert tasks[0].position == 0
    assert tasks[1].position == 1
    assert tasks[2].position == 2


def test_default_plan_title():

    result = create_plan_from_tasks(
        goal_title="Build autonomous JARVIS",
        tasks=[
            {
                "title": "Design planner",
            },
        ],
    )

    assert (
        result["plan"].title
        == "Plan for Build autonomous JARVIS"
    )


def test_default_task_priority():

    result = create_plan_from_tasks(
        goal_title="Test defaults",
        tasks=[
            {
                "title": "Task without priority",
            },
        ],
    )

    assert (
        result["tasks"][0].priority
        == "normal"
    )


def test_empty_goal_title():

    with pytest.raises(ValueError):

        create_plan_from_tasks(
            goal_title="",
            tasks=[
                {
                    "title": "Task",
                },
            ],
        )


def test_no_tasks():

    with pytest.raises(ValueError):

        create_plan_from_tasks(
            goal_title="Goal",
            tasks=[],
        )


def test_task_must_be_dictionary():

    with pytest.raises(ValueError):

        create_plan_from_tasks(
            goal_title="Goal",
            tasks=[
                "not a dictionary",
            ],
        )


def test_task_requires_title():

    with pytest.raises(ValueError):

        create_plan_from_tasks(
            goal_title="Goal",
            tasks=[
                {
                    "description": "Missing title",
                },
            ],
        )

def test_persist_planning_proposal():

    proposal = PlanningProposal(
        goal_title="Improve JARVIS",
        goal_description="Improve the COO system.",
        plan_title="COO improvement plan",
        plan_description="Implement improvements.",
        tasks=[
            TaskProposal(
                title="Analyze architecture",
                description="Review architecture.",
                priority="high",
            ),
            TaskProposal(
                title="Implement improvements",
                description="Make the required changes.",
                priority="normal",
            ),
        ],
    )

    result = persist_planning_proposal(
        proposal
    )

    assert result["goal"].title == (
        "Improve JARVIS"
    )

    assert result["plan"].title == (
        "COO improvement plan"
    )

    assert len(
        result["tasks"]
    ) == 2


def test_persist_requires_proposal():

    with pytest.raises(ValueError):

        persist_planning_proposal(
            "not a proposal"
        )

def test_persist_planning_proposal():

    proposal = PlanningProposal(
        goal_title="Improve JARVIS Conversations",
        goal_description=(
            "Improve natural multi-turn "
            "conversations."
        ),
        plan_title="Conversation Enhancement",
        plan_description=(
            "Improve conversational context "
            "and memory."
        ),
        tasks=[
            TaskProposal(
                title="Improve conversation flow",
                description=(
                    "Improve multi-turn conversation."
                ),
                priority="high",
                capability_status="partial",
                task_type="enhancement",
            ),
            TaskProposal(
                title="Integrate memory",
                description=(
                    "Integrate relevant memories."
                ),
                priority="high",
                capability_status="implemented",
                task_type="integration",
            ),
        ],
    )

    result = persist_planning_proposal(
        proposal
    )

    assert result["goal"].title == (
        "Improve JARVIS Conversations"
    )

    assert result["plan"].goal_id == (
        result["goal"].id
    )

    assert len(
        result["tasks"]
    ) == 2

    assert result["tasks"][0].position == 0
    assert result["tasks"][1].position == 1