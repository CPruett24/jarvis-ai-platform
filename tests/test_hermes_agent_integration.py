"""Hermes adapter/ACP integration with a deterministic transport boundary."""
from services.agents.hermes_acp import HermesACPConnection
from services.agents.hermes_agent import HermesAgent


def test_hermes_agent_acp_execution(monkeypatch, tmp_path):
    executable = tmp_path / "hermes.exe"
    executable.touch()
    connection = HermesACPConnection(executable=str(executable))
    calls = []
    monkeypatch.setattr(connection, "start", lambda: calls.append(("start",)))

    def send_request(method, params, timeout=30):
        calls.append((method, params, timeout))
        if method == "session/new":
            assert params == {"cwd": str(tmp_path), "mcpServers": []}
            return {"sessionId": "test-session"}
        assert method == "session/prompt"
        assert params == {
            "sessionId": "test-session",
            "prompt": [{"type": "text", "text": "Reply with exactly: JARVIS_HERMES_OK"}],
        }
        assert timeout == 30
        for text in ["JARVIS_", "HERMES_OK"]:
            connection._handle_message({
                "method": "session/update",
                "params": {"sessionId": "test-session", "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": text},
                }},
            })
        return {}

    monkeypatch.setattr(connection, "_send_request", send_request)
    agent = HermesAgent(connection=connection)
    try:
        result = agent.execute("Reply with exactly: JARVIS_HERMES_OK", cwd=str(tmp_path), timeout=30)
        assert result.success is True
        assert result.agent == "hermes"
        assert result.message == "JARVIS_HERMES_OK"
        assert result.data == {"session_id": "test-session"}
        assert [call[0] for call in calls] == ["start", "session/new", "session/prompt"]
        assert connection._notification_handlers == []
    finally:
        agent.close()
    assert connection._reader_stop.is_set()
