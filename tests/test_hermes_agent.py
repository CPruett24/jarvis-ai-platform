from services.agents.base_agent import (
    AgentExecutionResult,
)

from services.agents.hermes_agent import (
    HermesAgent,
)


def test_hermes_is_named_hermes():

    agent = HermesAgent()

    assert agent.name == "hermes"


def test_hermes_is_available_when_installed():

    agent = HermesAgent()

    assert agent.available is True


def test_hermes_adapter_executes_external_executor():

    calls = []

    def fake_executor(
        task,
        **kwargs,
    ):

        calls.append(
            (
                task,
                kwargs,
            )
        )

        return "Hermes completed the task."

    agent = HermesAgent(
        executor=fake_executor
    )

    assert agent.available is True

    result = agent.execute(
        "research AI agents",
        depth=2,
    )

    assert result.success is True
    assert result.agent == "hermes"
    assert result.message == (
        "Hermes completed the task."
    )

    assert calls == [
        (
            "research AI agents",
            {
                "depth": 2,
            },
        )
    ]


def test_hermes_preserves_structured_result():

    expected = AgentExecutionResult(
        success=True,
        agent="hermes",
        message="Research complete.",
        data={
            "sources": 5,
        },
    )

    agent = HermesAgent(
        executor=lambda task, **kwargs: expected
    )

    result = agent.execute(
        "research AI"
    )

    assert result is expected