from services.goal_service import create_goal
from services.plan_service import create_plan
from services.task_service import create_task
from models.planning_proposal import PlanningProposal


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

def persist_planning_proposal(
    proposal,
):
    """
    Persist a validated PlanningProposal.

    The proposal must already have been generated and
    validated by the AI planning layer.
    """

    if not isinstance(
        proposal,
        PlanningProposal,
    ):
        raise ValueError(
            "Expected a PlanningProposal."
        )

    tasks = [
        {
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
        }
        for task in proposal.tasks
    ]

    return create_plan_from_tasks(
        goal_title=proposal.goal_title,
        goal_description=proposal.goal_description,
        plan_title=proposal.plan_title,
        plan_description=proposal.plan_description,
        tasks=tasks,
    )