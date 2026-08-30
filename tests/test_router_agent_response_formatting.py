import commands.router as router


def test_router_cleans_agent_response_before_speaking(
    monkeypatch,
):

    spoken = []

    class FakeResult:

        success = True

        message = (
            "# Research Results\n\n"
            "Artificial intelligence is growing rapidly.[1]\n\n"
            "## Sources\n\n"
            "[1] https://example.com/source"
        )

        error = None

    def fake_execute_agent(
        agent_name,
        task,
        **kwargs,
    ):

        return FakeResult()

    def fake_speak(
        text,
    ):

        spoken.append(
            text
        )

    monkeypatch.setattr(
        router,
        "execute_agent",
        fake_execute_agent,
    )

    monkeypatch.setattr(
        router,
        "speak",
        fake_speak,
    )

    response = router.process(
        "research artificial intelligence trends",
        allow_interruption=False,
    )

    assert spoken

    assert (
        spoken[0]
        == response
    )

    assert "#" not in spoken[0]

    assert "[1]" not in spoken[0]

    assert "https://" not in spoken[0]

    assert "Sources" not in spoken[0]

    assert (
        "Artificial intelligence is growing rapidly."
        in spoken[0]
    )