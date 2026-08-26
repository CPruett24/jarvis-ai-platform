from services.agents.base_agent import (
    AgentExecutionResult,
    BaseAgent,
)


def test_base_agent_requires_execute():

    agent = BaseAgent()

    try:
        agent.execute("test task")
    except NotImplementedError:
        assert True
    else:
        assert False


def test_execution_result_defaults():

    result = AgentExecutionResult(
        success=True,
        agent="test",
    )

    assert result.success is True
    assert result.agent == "test"
    assert result.message == ""
    assert result.data == {}
    assert result.error is None