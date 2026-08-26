from dataclasses import dataclass, field


@dataclass
class AgentExecutionResult:
    """
    Structured result returned by an external JARVIS agent.
    """

    success: bool
    agent: str
    message: str = ""
    data: dict = field(default_factory=dict)
    error: str | None = None


class BaseAgent:
    """
    Interface implemented by external execution agents.
    """

    name = ""

    def execute(
        self,
        task,
        **kwargs,
    ):
        raise NotImplementedError