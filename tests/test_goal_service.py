import pytest

from models.database import Base, engine, SessionLocal
from models.goal import Goal

from services.goal_service import (
    create_goal,
    get_goal,
    get_active_goals,
    update_goal,
    activate_goal,
    complete_goal,
    cancel_goal,
)


@pytest.fixture(autouse=True)
def clean_goals():

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()

    yield

    db = SessionLocal()

    try:
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()


def test_create_goal():

    goal = create_goal(
        "Build JARVIS COO",
        "Build the executive coordination layer.",
        priority="critical",
    )

    assert goal.id is not None
    assert goal.title == "Build JARVIS COO"
    assert (
        goal.description
        == "Build the executive coordination layer."
    )
    assert goal.priority == "critical"
    assert goal.status == "planned"


def test_get_goal():

    created = create_goal(
        "Test goal"
    )

    goal = get_goal(
        created.id
    )

    assert goal is not None
    assert goal.id == created.id
    assert goal.title == "Test goal"


def test_get_missing_goal():

    goal = get_goal(
        999999
    )

    assert goal is None


def test_activate_goal():

    goal = create_goal(
        "Activate me"
    )

    updated = activate_goal(
        goal.id
    )

    assert updated.status == "active"


def test_get_active_goals():

    first = create_goal(
        "Active goal"
    )

    second = create_goal(
        "Planned goal"
    )

    activate_goal(
        first.id
    )

    active = get_active_goals()

    ids = [
        goal.id
        for goal in active
    ]

    assert first.id in ids
    assert second.id not in ids


def test_update_goal():

    goal = create_goal(
        "Original title"
    )

    updated = update_goal(
        goal.id,
        title="Updated title",
        description="New description",
        priority="high",
    )

    assert updated.title == "Updated title"
    assert (
        updated.description
        == "New description"
    )
    assert updated.priority == "high"
    assert updated.status == "planned"


def test_complete_goal():

    goal = create_goal(
        "Complete me"
    )

    activate_goal(
        goal.id
    )

    completed = complete_goal(
        goal.id
    )

    assert completed.status == "completed"


def test_cancel_goal():

    goal = create_goal(
        "Cancel me"
    )

    cancelled = cancel_goal(
        goal.id
    )

    assert cancelled.status == "cancelled"


def test_missing_goal_update():

    result = update_goal(
        999999,
        title="Does not exist",
    )

    assert result is None


def test_invalid_status():

    goal = create_goal(
        "Status test"
    )

    with pytest.raises(ValueError):

        update_goal(
            goal.id,
            status="invalid",
        )


def test_invalid_priority():

    with pytest.raises(ValueError):

        create_goal(
            "Priority test",
            priority="invalid",
        )


def test_empty_title():

    with pytest.raises(ValueError):

        create_goal(
            "",
        )