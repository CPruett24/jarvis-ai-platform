import pytest

from models.database import (
    Base,
    engine,
    SessionLocal,
)

from models.goal import Goal
from models.task import Task

from services.goal_service import create_goal

from services.task_service import (
    create_task,
    get_task,
    get_goal_tasks,
    get_active_tasks,
    update_task,
    activate_task,
    complete_task,
    pause_task,
    cancel_task,
)


@pytest.fixture(autouse=True)
def clean_tasks_and_goals():

    Base.metadata.create_all(
        bind=engine
    )

    db = SessionLocal()

    try:
        db.query(Task).delete()
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()

    yield

    db = SessionLocal()

    try:
        db.query(Task).delete()
        db.query(Goal).delete()
        db.commit()

    finally:
        db.close()


def test_create_task():

    goal = create_goal(
        "Build JARVIS COO"
    )

    task = create_task(
        goal.id,
        "Build task management",
        "Implement persistent task management.",
        priority="high",
    )

    assert task.id is not None
    assert task.goal_id == goal.id
    assert task.title == "Build task management"
    assert (
        task.description
        == "Implement persistent task management."
    )
    assert task.priority == "high"
    assert task.status == "pending"


def test_create_task_requires_existing_goal():

    with pytest.raises(ValueError):

        create_task(
            999999,
            "Invalid task",
        )


def test_get_task():

    goal = create_goal(
        "Test goal"
    )

    created = create_task(
        goal.id,
        "Test task",
    )

    task = get_task(
        created.id
    )

    assert task is not None
    assert task.id == created.id
    assert task.goal_id == goal.id


def test_get_missing_task():

    assert get_task(
        999999
    ) is None


def test_get_goal_tasks():

    goal = create_goal(
        "Goal with tasks"
    )

    first = create_task(
        goal.id,
        "First task",
        position=1,
    )

    second = create_task(
        goal.id,
        "Second task",
        position=2,
    )

    tasks = get_goal_tasks(
        goal.id
    )

    assert len(tasks) == 2
    assert tasks[0].id == first.id
    assert tasks[1].id == second.id


def test_tasks_are_isolated_by_goal():

    first_goal = create_goal(
        "First goal"
    )

    second_goal = create_goal(
        "Second goal"
    )

    first_task = create_task(
        first_goal.id,
        "First task",
    )

    second_task = create_task(
        second_goal.id,
        "Second task",
    )

    tasks = get_goal_tasks(
        first_goal.id
    )

    assert len(tasks) == 1
    assert tasks[0].id == first_task.id
    assert tasks[0].id != second_task.id


def test_activate_task():

    goal = create_goal(
        "Activation goal"
    )

    task = create_task(
        goal.id,
        "Activate me",
    )

    updated = activate_task(
        task.id
    )

    assert updated.status == "active"


def test_get_active_tasks():

    goal = create_goal(
        "Active task goal"
    )

    active = create_task(
        goal.id,
        "Active",
    )

    pending = create_task(
        goal.id,
        "Pending",
    )

    activate_task(
        active.id
    )

    tasks = get_active_tasks()

    ids = [
        task.id
        for task in tasks
    ]

    assert active.id in ids
    assert pending.id not in ids


def test_update_task():

    goal = create_goal(
        "Update goal"
    )

    task = create_task(
        goal.id,
        "Original",
    )

    updated = update_task(
        task.id,
        title="Updated",
        description="Updated description",
        priority="high",
        position=5,
    )

    assert updated.title == "Updated"
    assert (
        updated.description
        == "Updated description"
    )
    assert updated.priority == "high"
    assert updated.position == 5
    assert updated.status == "pending"


def test_complete_task():

    goal = create_goal(
        "Completion goal"
    )

    task = create_task(
        goal.id,
        "Complete me",
    )

    activate_task(
        task.id
    )

    completed = complete_task(
        task.id
    )

    assert completed.status == "completed"


def test_pause_task():

    goal = create_goal(
        "Pause goal"
    )

    task = create_task(
        goal.id,
        "Pause me",
    )

    activate_task(
        task.id
    )

    paused = pause_task(
        task.id
    )

    assert paused.status == "paused"


def test_cancel_task():

    goal = create_goal(
        "Cancel goal"
    )

    task = create_task(
        goal.id,
        "Cancel me",
    )

    cancelled = cancel_task(
        task.id
    )

    assert cancelled.status == "cancelled"


def test_invalid_status():

    goal = create_goal(
        "Status goal"
    )

    task = create_task(
        goal.id,
        "Status test",
    )

    with pytest.raises(ValueError):

        update_task(
            task.id,
            status="invalid",
        )


def test_invalid_priority():

    goal = create_goal(
        "Priority goal"
    )

    task = create_task(
        goal.id,
        "Priority test",
    )

    with pytest.raises(ValueError):

        update_task(
            task.id,
            priority="invalid",
        )


def test_empty_title():

    goal = create_goal(
        "Title goal"
    )

    with pytest.raises(ValueError):

        create_task(
            goal.id,
            "",
        )