from services.agents.base_agent import (
    AgentExecutionResult,
)

from services.agents.agent_manager import (
    execute_agent,
    get_agent,
    get_registered_agents,
    register_agent,
)


class FakeAgent:

    name = "fake"

    def execute(
        self,
        task,
        **kwargs,
    ):

        return AgentExecutionResult(
            success=True,
            agent="fake",
            message=f"Completed: {task}",
            data={
                "task": task,
            },
        )


def test_register_and_get_agent():

    agent = FakeAgent()

    register_agent(agent)

    assert get_agent("fake") is agent


def test_registered_agents_contains_agent():

    agent = FakeAgent()

    register_agent(agent)

    agents = get_registered_agents()

    assert agents["fake"] is agent


def test_execute_agent():

    agent = FakeAgent()

    register_agent(agent)

    result = execute_agent(
        "fake",
        "research this",
    )

    assert result.success is True
    assert result.agent == "fake"
    assert result.message == (
        "Completed: research this"
    )
    assert result.data["task"] == (
        "research this"
    )


def test_unknown_agent_returns_failure():

    result = execute_agent(
        "does_not_exist",
        "test",
    )

    assert result.success is False
    assert result.agent == (
        "does_not_exist"
    )
    assert result.error == (
        "Agent is not registered."
    )