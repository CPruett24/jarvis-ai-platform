import pytest

from models.database import (
    Base,
    engine,
    SessionLocal,
)

from models.goal import Goal
from models.plan import Plan
from models.task import Task

from services.goal_service import create_goal

from services.plan_service import (
    create_plan,
    get_plan,
    get_goal_plans,
    get_active_plans,
    update_plan,
    activate_plan,
    pause_plan,
    complete_plan,
    cancel_plan,
)


@pytest.fixture(autouse=True)
def clean_plans_goals_tasks():

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


def test_create_plan():

    goal = create_goal(
        "Build JARVIS COO"
    )

    plan = create_plan(
        goal.id,
        "Build executive architecture",
        "Create the persistent COO planning system.",
    )

    assert plan.id is not None
    assert plan.goal_id == goal.id
    assert plan.title == "Build executive architecture"
    assert (
        plan.description
        == "Create the persistent COO planning system."
    )
    assert plan.status == "draft"


def test_create_plan_requires_existing_goal():

    with pytest.raises(ValueError):

        create_plan(
            999999,
            "Invalid plan",
        )


def test_get_plan():

    goal = create_goal(
        "Test goal"
    )

    created = create_plan(
        goal.id,
        "Test plan",
    )

    plan = get_plan(
        created.id
    )

    assert plan is not None
    assert plan.id == created.id
    assert plan.goal_id == goal.id


def test_get_missing_plan():

    assert get_plan(
        999999
    ) is None


def test_get_goal_plans():

    goal = create_goal(
        "Goal with plans"
    )

    first = create_plan(
        goal.id,
        "First plan",
    )

    second = create_plan(
        goal.id,
        "Second plan",
    )

    plans = get_goal_plans(
        goal.id
    )

    assert len(plans) == 2
    assert plans[0].id == first.id
    assert plans[1].id == second.id


def test_plans_are_isolated_by_goal():

    first_goal = create_goal(
        "First goal"
    )

    second_goal = create_goal(
        "Second goal"
    )

    first_plan = create_plan(
        first_goal.id,
        "First plan",
    )

    second_plan = create_plan(
        second_goal.id,
        "Second plan",
    )

    plans = get_goal_plans(
        first_goal.id
    )

    assert len(plans) == 1
    assert plans[0].id == first_plan.id
    assert plans[0].id != second_plan.id


def test_activate_plan():

    goal = create_goal(
        "Activation goal"
    )

    plan = create_plan(
        goal.id,
        "Activate me",
    )

    updated = activate_plan(
        plan.id
    )

    assert updated.status == "active"


def test_get_active_plans():

    goal = create_goal(
        "Active plan goal"
    )

    active = create_plan(
        goal.id,
        "Active",
    )

    draft = create_plan(
        goal.id,
        "Draft",
    )

    activate_plan(
        active.id
    )

    plans = get_active_plans()

    ids = [
        plan.id
        for plan in plans
    ]

    assert active.id in ids
    assert draft.id not in ids


def test_update_plan():

    goal = create_goal(
        "Update goal"
    )

    plan = create_plan(
        goal.id,
        "Original",
    )

    updated = update_plan(
        plan.id,
        title="Updated",
        description="Updated description",
    )

    assert updated.title == "Updated"
    assert (
        updated.description
        == "Updated description"
    )
    assert updated.status == "draft"


def test_pause_plan():

    goal = create_goal(
        "Pause goal"
    )

    plan = create_plan(
        goal.id,
        "Pause me",
    )

    activate_plan(
        plan.id
    )

    paused = pause_plan(
        plan.id
    )

    assert paused.status == "paused"


def test_complete_plan():

    goal = create_goal(
        "Completion goal"
    )

    plan = create_plan(
        goal.id,
        "Complete me",
    )

    activate_plan(
        plan.id
    )

    completed = complete_plan(
        plan.id
    )

    assert completed.status == "completed"


def test_cancel_plan():

    goal = create_goal(
        "Cancel goal"
    )

    plan = create_plan(
        goal.id,
        "Cancel me",
    )

    cancelled = cancel_plan(
        plan.id
    )

    assert cancelled.status == "cancelled"


def test_invalid_status():

    goal = create_goal(
        "Status goal"
    )

    plan = create_plan(
        goal.id,
        "Status test",
    )

    with pytest.raises(ValueError):

        update_plan(
            plan.id,
            status="invalid",
        )


def test_empty_title():

    goal = create_goal(
        "Title goal"
    )

    with pytest.raises(ValueError):

        create_plan(
            goal.id,
            "",
        )