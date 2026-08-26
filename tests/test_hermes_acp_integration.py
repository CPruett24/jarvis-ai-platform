import pytest

from services.agents.hermes_acp import (
    HermesACPConnection,
)


@pytest.mark.integration
def test_real_hermes_acp_connection():

    connection = HermesACPConnection()

    if not connection.available:
        pytest.skip(
            "Hermes executable is not installed."
        )

    try:

        result = connection.execute(
            "Reply with exactly: "
            "Hermes connection successful.",
            cwd=r"C:\Projects\JARVIS-AI",
            timeout=300,
        )

        assert result["success"] is True
        assert result["session_id"]
        assert (
            "Hermes connection successful."
            in result["message"]
        )

    finally:

        connection.close()
