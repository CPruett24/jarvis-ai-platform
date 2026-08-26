from services.agents.hermes_agent import HermesAgent


def test_hermes_agent_real_execution():

    agent = HermesAgent()

    try:
        result = agent.execute(
            "Reply with exactly: JARVIS_HERMES_OK",
            cwd=r"C:\Projects\JARVIS-AI",
            timeout=30,
        )

        print("\nREAL HERMES RESULT:")
        print("success:", result.success)
        print("message:", result.message)
        print("error:", result.error)

        assert result.success is True
        assert result.message == "JARVIS_HERMES_OK"

    finally:
        agent.close()
