from models.information import (
    InformationSource,
)

import services.memory_service as memory_service


def test_get_memory_information(
    monkeypatch,
):

    class FakeMemory:

        content = (
            "Your project deadline is Friday."
        )

    monkeypatch.setattr(
        memory_service,
        "get_memories",
        lambda: [
            FakeMemory()
        ],
    )

    information = (
        memory_service.get_memory_information()
    )

    assert len(
        information
    ) == 1

    assert (
        information[0].content
        == "Your project deadline is Friday."
    )

    assert (
        information[0].source
        == InformationSource.REMEMBERED
    )