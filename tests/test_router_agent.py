import pytest
from services.agents.hermes_agent import HermesAgent
from commands import router


@pytest.fixture(autouse=True)
def installed_hermes(monkeypatch):
    # Exercise router availability admission without depending on the host installation.
    monkeypatch.setattr(HermesAgent, "available", property(lambda self: True))


def test_router_delegates_agent_request(
    monkeypatch,
):
    executed = {}
    saved_messages = []

    class FakeResult:
        success = True
        message = "Research completed."
        error = None

    def fake_execute_agent(
        agent_name,
        task,
        **kwargs,
    ):
        executed["agent_name"] = agent_name
        executed["task"] = task

        return FakeResult()

    monkeypatch.setattr(
        router,
        "execute_agent",
        fake_execute_agent,
    )

    monkeypatch.setattr(
        router,
        "speak",
        lambda text: None,
    )

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
        )

    monkeypatch.setattr(
        router,
        "add_message",
        fake_add_message,
    )

    response = router.process(
        "research artificial intelligence trends",
        allow_interruption=False,
    )

    assert (
        executed["agent_name"]
        == "hermes"
    )

    assert (
        executed["task"]
        == "artificial intelligence trends"
    )

    assert (
        response
        == "Research completed."
    )

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": (
                    "research artificial intelligence trends"
                ),
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "[agent_result] Research completed.",
                "source": "hermes",
            },
            {
                "role": "assistant",
                "message": "Research completed.",
                "source": "hermes",
            },
        ]
    )

def test_router_persists_agent_request_and_response(
    monkeypatch,
):
    saved_messages = []

    class FakeResult:
        success = True
        message = "Research completed."
        error = None

    def fake_execute_agent(
        agent_name,
        task,
        **kwargs,
    ):
        return FakeResult()

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {"role": role, "message": message, "source": source}
        )

    monkeypatch.setattr(
        router,
        "execute_agent",
        fake_execute_agent,
    )

    monkeypatch.setattr(
        router,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        router,
        "speak",
        lambda text: None,
    )

    response = router.process(
        "research artificial intelligence trends",
        allow_interruption=False,
    )

    assert (
        response
        == "Research completed."
    )

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": (
                    "research artificial intelligence trends"
                ),
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "[agent_result] Research completed.",
                "source": "hermes",
            },
            {
                "role": "assistant",
                "message": "Research completed.",
                "source": "hermes",
            },
        ]
    )