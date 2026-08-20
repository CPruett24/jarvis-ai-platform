from models.database import SessionLocal
from models.task import Task
from models.goal import Goal


VALID_STATUSES = {
    "pending",
    "active",
    "paused",
    "completed",
    "cancelled",
    "failed",
}


VALID_PRIORITIES = {
    "low",
    "normal",
    "high",
    "critical",
}


def create_task(
    goal_id,
    title,
    description=None,
    priority="normal",
    position=0,
):
    """
    Create and persist a task belonging to a goal.
    """

    if not title or not title.strip():
        raise ValueError(
            "Task title cannot be empty."
        )

    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority: {priority}"
        )

    db = SessionLocal()

    try:
        goal = db.get(
            Goal,
            goal_id,
        )

        if goal is None:
            raise ValueError(
                f"Goal {goal_id} does not exist."
            )

        task = Task(
            goal_id=goal_id,
            title=title.strip(),
            description=description,
            priority=priority,
            position=position,
            status="pending",
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return task

    finally:
        db.close()


def get_task(task_id):
    """
    Retrieve a task by ID.
    """

    db = SessionLocal()

    try:
        return db.get(
            Task,
            task_id,
        )

    finally:
        db.close()


def get_goal_tasks(goal_id):
    """
    Return tasks belonging to a goal,
    ordered by position and creation time.
    """

    db = SessionLocal()

    try:
        return (
            db.query(Task)
            .filter(
                Task.goal_id == goal_id
            )
            .order_by(
                Task.position.asc(),
                Task.created_at.asc(),
            )
            .all()
        )

    finally:
        db.close()


def get_active_tasks():
    """
    Return all tasks currently being worked on.
    """

    db = SessionLocal()

    try:
        return (
            db.query(Task)
            .filter(
                Task.status == "active"
            )
            .order_by(
                Task.priority.desc(),
                Task.created_at.asc(),
            )
            .all()
        )

    finally:
        db.close()


def update_task(
    task_id,
    title=None,
    description=None,
    status=None,
    priority=None,
    position=None,
):
    """
    Update supplied fields on an existing task.
    """

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority: {priority}"
        )

    db = SessionLocal()

    try:
        task = db.get(
            Task,
            task_id,
        )

        if task is None:
            return None

        if title is not None:

            if not title.strip():
                raise ValueError(
                    "Task title cannot be empty."
                )

            task.title = title.strip()

        if description is not None:
            task.description = description

        if status is not None:
            task.status = status

        if priority is not None:
            task.priority = priority

        if position is not None:
            task.position = position

        db.commit()
        db.refresh(task)

        return task

    finally:
        db.close()


def activate_task(task_id):
    """
    Mark a task as active.
    """

    return update_task(
        task_id,
        status="active",
    )


def complete_task(task_id):
    """
    Mark a task as completed.
    """

    return update_task(
        task_id,
        status="completed",
    )


def pause_task(task_id):
    """
    Pause an active task.
    """

    return update_task(
        task_id,
        status="paused",
    )


def cancel_task(task_id):
    """
    Cancel a task.
    """

    return update_task(
        task_id,
        status="cancelled",
    )