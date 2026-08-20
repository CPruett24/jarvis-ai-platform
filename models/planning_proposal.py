from dataclasses import dataclass, field


@dataclass
class TaskProposal:

    title: str

    description: str | None = None

    priority: str = "normal"

    capability_status: str = "missing"

    task_type: str = "implementation"


@dataclass
class PlanningProposal:

    goal_title: str

    goal_description: str | None = None

    plan_title: str | None = None

    plan_description: str | None = None

    tasks: list[TaskProposal] = field(
        default_factory=list
    )