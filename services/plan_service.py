from models.database import SessionLocal
from models.plan import Plan
from models.goal import Goal


VALID_STATUSES = {
    "draft",
    "active",
    "paused",
    "completed",
    "cancelled",
}


def create_plan(
    goal_id,
    title,
    description=None,
):
    """
    Create and persist a plan belonging to a goal.
    """

    if not title or not title.strip():
        raise ValueError(
            "Plan title cannot be empty."
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

        plan = Plan(
            goal_id=goal_id,
            title=title.strip(),
            description=description,
            status="draft",
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)

        return plan

    finally:
        db.close()


def get_plan(plan_id):
    """
    Retrieve a plan by ID.
    """

    db = SessionLocal()

    try:
        return db.get(
            Plan,
            plan_id,
        )

    finally:
        db.close()


def get_goal_plans(goal_id):
    """
    Return all plans belonging to a goal.
    """

    db = SessionLocal()

    try:
        return (
            db.query(Plan)
            .filter(
                Plan.goal_id == goal_id
            )
            .order_by(
                Plan.created_at.asc()
            )
            .all()
        )

    finally:
        db.close()


def get_active_plans():
    """
    Return currently active plans.
    """

    db = SessionLocal()

    try:
        return (
            db.query(Plan)
            .filter(
                Plan.status == "active"
            )
            .order_by(
                Plan.created_at.asc()
            )
            .all()
        )

    finally:
        db.close()


def update_plan(
    plan_id,
    title=None,
    description=None,
    status=None,
):
    """
    Update supplied fields on an existing plan.
    """

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status: {status}"
        )

    db = SessionLocal()

    try:
        plan = db.get(
            Plan,
            plan_id,
        )

        if plan is None:
            return None

        if title is not None:

            if not title.strip():
                raise ValueError(
                    "Plan title cannot be empty."
                )

            plan.title = title.strip()

        if description is not None:
            plan.description = description

        if status is not None:
            plan.status = status

        db.commit()
        db.refresh(plan)

        return plan

    finally:
        db.close()


def activate_plan(plan_id):
    """
    Mark a plan as active.
    """

    return update_plan(
        plan_id,
        status="active",
    )


def pause_plan(plan_id):
    """
    Pause an active plan.
    """

    return update_plan(
        plan_id,
        status="paused",
    )


def complete_plan(plan_id):
    """
    Mark a plan as completed.
    """

    return update_plan(
        plan_id,
        status="completed",
    )


def cancel_plan(plan_id):
    """
    Mark a plan as cancelled.
    """

    return update_plan(
        plan_id,
        status="cancelled",
    )