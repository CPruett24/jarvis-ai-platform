from services.goal_service import create_goal
from services.plan_service import create_plan
from services.task_service import create_task


def create_plan_from_tasks(
    goal_title,
    tasks,
    goal_description=None,
    plan_title=None,
    plan_description=None,
):
    """
    Create a goal, plan, and ordered tasks from a structured
    planning request.

    `tasks` should be a list of dictionaries containing:

        {
            "title": "...",
            "description": "...",
            "priority": "normal"
        }

    Returns a dictionary containing the persisted goal,
    plan, and tasks.
    """

    if not goal_title or not goal_title.strip():
        raise ValueError(
            "Goal title cannot be empty."
        )

    if not tasks:
        raise ValueError(
            "At least one task is required."
        )

    goal = create_goal(
        title=goal_title,
        description=goal_description,
    )

    plan = create_plan(
        goal_id=goal.id,
        title=(
            plan_title.strip()
            if plan_title
            else f"Plan for {goal.title}"
        ),
        description=plan_description,
    )

    created_tasks = []

    for position, task_data in enumerate(tasks):

        if not isinstance(task_data, dict):
            raise ValueError(
                "Each task must be a dictionary."
            )

        title = task_data.get("title")

        if not title:
            raise ValueError(
                "Every task must have a title."
            )

        task = create_task(
            goal_id=goal.id,
            title=title,
            description=task_data.get(
                "description"
            ),
            priority=task_data.get(
                "priority",
                "normal",
            ),
            position=position,
        )

        created_tasks.append(task)

    return {
        "goal": goal,
        "plan": plan,
        "tasks": created_tasks,
    }