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