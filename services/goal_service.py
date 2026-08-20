from models.database import SessionLocal
from models.goal import Goal


VALID_STATUSES = {
    "planned",
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


def create_goal(
    title,
    description=None,
    priority="normal",
):
    """
    Create and persist a new JARVIS goal.
    """

    if not title or not title.strip():
        raise ValueError(
            "Goal title cannot be empty."
        )

    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority: {priority}"
        )

    db = SessionLocal()

    try:
        goal = Goal(
            title=title.strip(),
            description=description,
            priority=priority,
            status="planned",
        )

        db.add(goal)
        db.commit()
        db.refresh(goal)

        return goal

    finally:
        db.close()


def get_goal(goal_id):
    """
    Retrieve a goal by ID.
    """

    db = SessionLocal()

    try:
        return db.get(
            Goal,
            goal_id,
        )

    finally:
        db.close()


def get_active_goals():
    """
    Return all goals currently considered active.
    """

    db = SessionLocal()

    try:
        return (
            db.query(Goal)
            .filter(
                Goal.status == "active"
            )
            .order_by(
                Goal.priority.desc(),
                Goal.created_at.asc(),
            )
            .all()
        )

    finally:
        db.close()


def update_goal(
    goal_id,
    title=None,
    description=None,
    status=None,
    priority=None,
):
    """
    Update fields on an existing goal.

    Only supplied fields are changed.
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
        goal = db.get(
            Goal,
            goal_id,
        )

        if goal is None:
            return None

        if title is not None:
            if not title.strip():
                raise ValueError(
                    "Goal title cannot be empty."
                )

            goal.title = title.strip()

        if description is not None:
            goal.description = description

        if status is not None:
            goal.status = status

        if priority is not None:
            goal.priority = priority

        db.commit()
        db.refresh(goal)

        return goal

    finally:
        db.close()


def activate_goal(goal_id):
    """
    Mark a planned or paused goal as active.
    """

    return update_goal(
        goal_id,
        status="active",
    )


def complete_goal(goal_id):
    """
    Mark a goal as completed.
    """

    return update_goal(
        goal_id,
        status="completed",
    )


def cancel_goal(goal_id):
    """
    Mark a goal as cancelled.
    """

    return update_goal(
        goal_id,
        status="cancelled",
    )