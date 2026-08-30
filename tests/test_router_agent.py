from commands import router


def test_router_delegates_agent_request(
    monkeypatch,
):
    executed = {}

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