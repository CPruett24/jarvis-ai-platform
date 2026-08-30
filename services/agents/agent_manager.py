from services.agents.base_agent import (
    AgentExecutionResult,
)


_AGENTS = {}


def register_agent(
    agent,
):
    """
    Register an agent by its canonical name.
    """

    if not agent.name:
        raise ValueError(
            "Agent must define a name."
        )

    _AGENTS[agent.name] = agent


def get_agent(
    agent_name,
):
    return _AGENTS.get(
        agent_name
    )


def get_registered_agents():
    return dict(_AGENTS)


def execute_agent(
    agent_name,
    task,
    **kwargs,
):
    """
    Execute a registered agent.
    """

    agent = get_agent(
        agent_name
    )

    if agent is None:

        return AgentExecutionResult(
            success=False,
            agent=agent_name,
            error="Agent is not registered.",
        )

    try:

        return agent.execute(
            task,
            **kwargs,
        )

    except Exception as exc:

        return AgentExecutionResult(
            success=False,
            agent=agent_name,
            error=str(exc),
        )


def stream_agent(
    agent_name,
    task,
    **kwargs,
):
    """
    Stream response chunks from a registered agent.
    """

    agent = get_agent(
        agent_name
    )

    if agent is None:

        raise RuntimeError(
            "Agent is not registered."
        )

    yield from agent.stream(
        task,
        **kwargs,
    )