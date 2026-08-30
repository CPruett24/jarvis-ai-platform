from services.agents.base_agent import (
    BaseAgent,
    AgentExecutionResult,
)

from services.agents.hermes_acp import (
    HermesACPConnection,
)


class HermesAgent(BaseAgent):
    """
    JARVIS adapter for the external Hermes Agent.

    Hermes runs as an independent process and JARVIS
    communicates with it through ACP.
    """

    name = "hermes"

    def __init__(
        self,
        executor=None,
        connection=None,
    ):
        self.executor = executor
        self.connection = connection

    @property
    def available(self):

        if self.executor is not None:
            return True

        if self.connection is not None:
            return self.connection.available

        return HermesACPConnection().available

    def execute(
        self,
        task,
        **kwargs,
    ):

        # Preserve dependency injection for unit tests.
        if self.executor is not None:

            try:

                result = self.executor(
                    task,
                    **kwargs,
                )

                if isinstance(
                    result,
                    AgentExecutionResult,
                ):
                    return result

                return AgentExecutionResult(
                    success=True,
                    agent=self.name,
                    message=str(result),
                    data={
                        "result": result,
                    },
                )

            except Exception as exc:

                return AgentExecutionResult(
                    success=False,
                    agent=self.name,
                    error=str(exc),
                )

        if not self.available:

            return AgentExecutionResult(
                success=False,
                agent=self.name,
                error=(
                    "Hermes is not installed or "
                    "configured."
                ),
            )

        try:

            if self.connection is None:
                self.connection = (
                    HermesACPConnection()
                )

            result = self.connection.execute(
                task,
                cwd=kwargs.get(
                    "cwd"
                ),
                timeout=kwargs.get(
                    "timeout",
                    300,
                ),
            )

            return AgentExecutionResult(
                success=result["success"],
                agent=self.name,
                message=result["message"],
                data={
                    "session_id":
                        result["session_id"],
                },
            )

        except Exception as exc:

            return AgentExecutionResult(
                success=False,
                agent=self.name,
                error=str(exc),
            )

    def stream(
        self,
        task,
        **kwargs,
    ):
        """
        Stream response chunks from Hermes.

        A new ACP session is created for the task and each
        Hermes agent_message_chunk is yielded immediately.
        """

        if not self.available:

            raise RuntimeError(
                "Hermes is not installed or configured."
            )

        if self.executor is not None:

            result = self.executor(
                task,
                **kwargs,
            )

            if isinstance(
                result,
                AgentExecutionResult,
            ):

                if not result.success:
                    raise RuntimeError(
                        result.error
                        or "Hermes execution failed."
                    )

                if result.message:
                    yield result.message

                return

            if result is not None:
                yield str(result)

            return

        if self.connection is None:

            self.connection = (
                HermesACPConnection()
            )

        self.connection.start()

        session_id = (
            self.connection.create_session(
                cwd=kwargs.get(
                    "cwd"
                )
            )
        )

        timeout = kwargs.get(
            "timeout",
            300,
        )

        for chunk in self.connection.stream_prompt(
            session_id,
            task,
            timeout=timeout,
        ):
            yield chunk

    def close(self):

        if self.connection is not None:
            self.connection.close()