import json

from ollama import chat

from models.planning_proposal import (
    PlanningProposal,
    TaskProposal,
)

from services.project_context import (
    get_relevant_project_context,
    get_relevant_project_analysis,
    get_project_capabilities,
)

PLANNER_MODEL = "llama3.1:8b"


SYSTEM_PROMPT = """
You are JARVIS, an experienced COO and senior software
engineering planner.

Your job is to turn a user's objective into a practical,
ordered execution plan for the EXISTING JARVIS project.

The project context supplied with the request describes the
current codebase, its architecture, documentation, roadmap,
and current implementation state.

Treat the current project state and source-code analysis as
authoritative for what currently exists.

Return ONLY valid JSON.

The JSON must have exactly this structure:

{
  "goal_title": "string",
  "goal_description": "string",
  "plan_title": "string",
  "plan_description": "string",
  "tasks": [
    {
      "title": "string",
      "description": "string",
      "priority": "low|normal|high|critical"
    }
  ]
}

Planning rules:

1. Create concrete, actionable tasks.

2. Tasks should be ordered logically.

3. Do not invent completed work.

4. Do not assume planned roadmap items are already implemented.

5. Do not recommend rebuilding capabilities that already exist.

6. Prefer extending existing services, models, and architecture
   over creating duplicate systems.

7. Reference existing files, services, or components in task
   descriptions whenever that improves the plan.

8. Do not recommend training or fine-tuning a language model
   unless the project context or the user's objective explicitly
   requires it.

9. Do not invent external systems, agents, tools, or capabilities
   as if they already exist.

10. If a capability does not exist yet, propose implementing it
    using the architecture that already exists.

11. Keep the number of tasks reasonable.

12. Prefer tasks that can be independently verified or tested.

13. Use only these priorities:
    low, normal, high, critical.

14. Do not include markdown.

15. Do not include explanations outside the JSON.

16. The goal is to improve the existing JARVIS project, not
    design an unrelated replacement system.

17. Distinguish between:
    - what exists today,
    - what the project plans to build,
    - what needs to be implemented.

18. Do not create a task simply to recreate a file, service,
    model, or capability that the project context shows already
    exists.

CAPABILITY STATUS AND TASK TYPE ARE DIFFERENT CONCEPTS.

capability_status describes the current state of the capability
being affected by the task.

task_type describes what the proposed task actually does.

Valid capability_status values:

- "implemented"
- "partial"
- "missing"

Valid task_type values:

- "implementation"
- "enhancement"
- "integration"
- "refactor"
- "testing"

Examples:

If long-term memory storage already exists but needs to be
connected to conversational reasoning:

capability_status = "implemented"
task_type = "integration"

If conversational reasoning exists but needs substantial
improvement:

capability_status = "partial"
task_type = "enhancement"

If agent delegation does not exist:

capability_status = "missing"
task_type = "implementation"

If an existing capability needs structural cleanup:

capability_status = "implemented"
task_type = "refactor"

If an existing capability specifically needs additional tests:

capability_status = "implemented"
task_type = "testing"

The capability status describes the capability being affected.
It does NOT describe whether the proposed task itself has
already been completed.

The CURRENT JARVIS CAPABILITIES registry is authoritative
when determining capability_status.

Never claim that an implemented capability is missing.

Never create an implementation task for a capability that is
already implemented.

When a capability is partial, prefer enhancement, integration,
refactor, or testing rather than rebuilding it.

The project documentation may contain historical limitations.
Never assume a documented limitation is still missing if the
CURRENT JARVIS CAPABILITIES registry says it is implemented
or partial.
"""

PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "goal_title": {
            "type": "string",
        },
        "goal_description": {
            "type": "string",
        },
        "plan_title": {
            "type": "string",
        },
        "plan_description": {
            "type": "string",
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "description": {
                        "type": "string",
                    },
                    "priority": {
                        "type": "string",
                        "enum": [
                            "low",
                            "normal",
                            "high",
                            "critical",
                        ],
                    },
                    "capability_status": {
                        "type": "string",
                        "enum": [
                            "implemented",
                            "partial",
                            "missing",
                        ],
                    },
                    "task_type": {
                        "type": "string",
                        "enum": [
                            "implementation",
                            "enhancement",
                            "integration",
                            "refactor",
                            "testing",
                        ],
                    },
                },
                "required": [
                    "title",
                    "description",
                    "priority",
                    "capability_status",
                    "task_type",
                ],
            },
        },
    },
    "required": [
        "goal_title",
        "goal_description",
        "plan_title",
        "plan_description",
        "tasks",
    ],
}


def _extract_json(text):
    """
    Extract a JSON object from model output.

    Handles:
    - Plain JSON
    - JSON inside markdown code fences
    - JSON surrounded by normal model prose
    """

    text = text.strip()

    # First, try the complete response directly.
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Remove markdown code fences if present.
    if "```" in text:

        parts = text.split("```")

        for part in parts:

            candidate = part.strip()

            if candidate.startswith("json"):

                candidate = candidate[4:].strip()

            try:
                return json.loads(candidate)

            except json.JSONDecodeError:
                continue

    # Look for a JSON object embedded inside surrounding text.
    start = text.find("{")

    if start == -1:
        raise json.JSONDecodeError(
            "No JSON object found",
            text,
            0,
        )

    depth = 0
    in_string = False
    escape = False

    for index in range(
        start,
        len(text),
    ):

        character = text[index]

        if in_string:

            if escape:

                escape = False

            elif character == "\\":

                escape = True

            elif character == '"':

                in_string = False

            continue

        if character == '"':

            in_string = True

            continue

        if character == "{":

            depth += 1

        elif character == "}":

            depth -= 1

            if depth == 0:

                candidate = text[
                    start:index + 1
                ]

                return json.loads(
                    candidate
                )

    raise json.JSONDecodeError(
        "Incomplete JSON object",
        text,
        start,
    )


def _validate_proposal(data):
    """
    Validate and convert raw AI planning output into a
    PlanningProposal.

    The AI output is treated as untrusted input.
    """

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Planning proposal must be a dictionary."
        )

    goal_title = data.get(
        "goal_title"
    )

    if not goal_title:

        raise ValueError(
            "Planning proposal requires "
            "a goal_title."
        )

    goal_description = data.get(
        "goal_description"
    )

    plan_title = data.get(
        "plan_title"
    )

    plan_description = data.get(
        "plan_description"
    )

    raw_tasks = data.get(
        "tasks",
        [],
    )

    if not isinstance(
        raw_tasks,
        list,
    ):
        raise ValueError(
            "Planning proposal tasks "
            "must be a list."
        )

    task_proposals = []

    valid_priorities = {
        "low",
        "normal",
        "high",
        "critical",
    }

    valid_capability_statuses = {
        "implemented",
        "partial",
        "missing",
    }

    valid_task_types = {
        "implementation",
        "enhancement",
        "integration",
        "refactor",
        "testing",
    }

    for task in raw_tasks:

        if not isinstance(
            task,
            dict,
        ):
            raise ValueError(
                "Each planning task "
                "must be a dictionary."
            )

        title = task.get(
            "title"
        )

        if not title:

            raise ValueError(
                "Every planning task "
                "requires a title."
            )

        description = task.get(
            "description"
        )

        priority = task.get(
            "priority",
            "normal",
        )

        if priority not in valid_priorities:

            raise ValueError(
                "Invalid task priority: "
                f"{priority}"
            )

        capability_status = task.get(
            "capability_status",
            "missing",
        )

        if (
            capability_status
            not in valid_capability_statuses
        ):

            raise ValueError(
                "Invalid capability status: "
                f"{capability_status}"
            )

        task_type = task.get(
            "task_type",
            "implementation",
        )

        if (
            task_type
            not in valid_task_types
        ):

            raise ValueError(
                "Invalid task type: "
                f"{task_type}"
            )

        task_proposals.append(
            TaskProposal(
                title=title.strip(),
                description=description,
                priority=priority,
                capability_status=(
                    capability_status
                ),
                task_type=task_type,
            )
        )

    return PlanningProposal(
        goal_title=goal_title.strip(),
        goal_description=goal_description,
        plan_title=plan_title,
        plan_description=plan_description,
        tasks=task_proposals,
    )

def _validate_capability_statuses(
    proposal,
):
    """
    Reconcile AI-generated capability statuses and task types
    with the authoritative project capability registry.

    The capability registry is authoritative for current
    capability status.

    Task type describes the work being proposed and is normalized
    based on the capability's current status.
    """

    from services.project_context import (
        get_all_capabilities,
        get_capability_status,
    )

    all_capabilities = (
        get_all_capabilities()
    )

    capability_aliases = {
        "natural multi-turn conversational reasoning":
            "natural_multi_turn_conversational_reasoning",

        "multi-turn conversational reasoning":
            "natural_multi_turn_conversational_reasoning",

        "long-term memory":
            "long_term_memory_storage",

        "long-term memory storage":
            "long_term_memory_storage",

        "memory search":
            "memory_search",

        "memory deletion":
            "memory_deletion",

        "memory integration":
            "memory_integration",

        "conversation topic tracking":
            "conversation_topic_tracking",

        "multi-file project context":
            "multi_file_project_context",

        "autonomous multi-step plan execution":
            "autonomous_multi_step_plan_execution",

        "agent delegation":
            "agent_delegation",

        "agent task execution":
            "agent_task_execution",
    }

    for task in proposal.tasks:

        text = (
            task.title
            + " "
            + (
                task.description
                or ""
            )
        ).lower()

        matched_capabilities = []

        # First use explicit aliases for common
        # human-readable capability names.
        for phrase, capability in (
            capability_aliases.items()
        ):

            if phrase in text:

                matched_capabilities.append(
                    capability
                )

        # Then fall back to matching the actual
        # registry capability names.
        for capabilities in (
            all_capabilities.values()
        ):

            for capability in (
                capabilities
            ):

                readable = (
                    capability
                    .replace("_", " ")
                    .lower()
                )

                if readable in text:

                    matched_capabilities.append(
                        capability
                    )

        # Remove duplicates while preserving
        # order.
        matched_capabilities = list(
            dict.fromkeys(
                matched_capabilities
            )
        )

        if not matched_capabilities:
            continue

        statuses = []

        for capability in (
            matched_capabilities
        ):

            status = (
                get_capability_status(
                    capability
                )
            )

            if status:

                statuses.append(
                    status
                )

        if not statuses:
            continue

        # Determine the authoritative status.
        #
        # Implemented takes precedence when a task
        # touches an implemented capability.
        if "implemented" in statuses:

            task.capability_status = (
                "implemented"
            )

        elif "partial" in statuses:

            task.capability_status = (
                "partial"
            )

        else:

            task.capability_status = (
                "missing"
            )

        # Normalize the proposed work based on
        # the capability's actual state.
        if task.capability_status == "implemented":

            if task.task_type == (
                "implementation"
            ):

                task.task_type = (
                    "integration"
                )

        elif task.capability_status == "partial":

            if task.task_type == (
                "implementation"
            ):

                task.task_type = (
                    "enhancement"
                )

    return proposal

def _filter_out_of_scope_tasks(
    proposal,
    objective,
):
    """
    Remove clearly unrelated future capabilities from a plan.

    This is intentionally conservative.

    A task is removed only when it is clearly an autonomous
    agent/planning capability that is unrelated to the user's
    current objective.

    We do not attempt to determine relevance solely through
    keyword matching for ordinary project tasks.
    """

    objective_text = (
        objective
        .lower()
        .strip()
    )

    conversation_objective = any(
        phrase in objective_text
        for phrase in (
            "conversation",
            "conversational",
            "multi-turn",
            "context",
            "memory",
            "remember",
            "dialogue",
        )
    )

    if not conversation_objective:

        return proposal

    autonomy_keywords = (
        "autonomous multi-step plan execution",
        "agent delegation",
        "agent task execution",
        "agent orchestration",
    )

    filtered_tasks = []

    for task in proposal.tasks:

        task_text = (
            task.title
            + " "
            + (
                task.description
                or ""
            )
        ).lower()

        is_unrelated_autonomy_task = any(
            keyword in task_text
            for keyword in autonomy_keywords
        )

        if is_unrelated_autonomy_task:

            continue

        filtered_tasks.append(
            task
        )

    proposal.tasks = filtered_tasks

    return proposal

def generate_planning_proposal(objective):
    """
    Ask the configured AI model to generate a structured,
    project-aware planning proposal.

    This function does NOT create database records.
    """

    if not objective or not objective.strip():
        raise ValueError(
            "Planning objective cannot be empty."
        )

    project_documentation = get_relevant_project_context(
        objective.strip()
    )

    project_analysis = get_relevant_project_analysis(
        objective.strip()
    )

    project_capabilities = get_project_capabilities()

    user_prompt = (
        "USER OBJECTIVE:\n\n"
        f"{objective.strip()}\n\n"

        "AUTHORITATIVE CURRENT CAPABILITY REGISTRY:\n\n"
        f"{project_capabilities}\n\n"

        "RELEVANT PROJECT DOCUMENTATION:\n\n"
        f"{project_documentation}\n\n"

        "RELEVANT CURRENT CODE ANALYSIS:\n\n"
        f"{project_analysis}\n\n"

        "Create a project-specific execution plan for the "
        "USER OBJECTIVE.\n\n"

        "The capability registry is authoritative for the current "
        "implementation status of major capabilities.\n\n"

        "Use current code analysis as supporting technical evidence.\n\n"

        "Use project documentation to understand the intended "
        "direction of JARVIS.\n\n"

        "Only propose work that contributes directly to the user's "
        "objective.\n\n"

        "Do not create redundant implementation tasks for "
        "capabilities already marked as implemented.\n\n"

        "For every task, provide both capability_status and "
        "task_type.\n\n"

        "Remember that capability_status describes the capability "
        "being affected, while task_type describes the work being "
        "proposed."
    )

    response = chat(
        model=PLANNER_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        format=PLANNING_SCHEMA,
    )

    content = response[
        "message"
    ][
        "content"
    ]

    data = _extract_json(
        content
    )

    proposal = _validate_proposal(
        data
    )

    proposal = _validate_capability_statuses(
        proposal
    )

    proposal = _filter_out_of_scope_tasks(
        proposal,
        objective,
    )

    return proposal