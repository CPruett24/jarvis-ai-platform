import pytest

from commands import router
from services import conversation_manager as conversation


@pytest.fixture(autouse=True)
def isolated_state():
    conversation.clear_topic()
    conversation.clear_pending_request()

    yield

    conversation.clear_topic()
    conversation.clear_pending_request()


@pytest.mark.parametrize(
    "command",
    [
        "remember that my preferred editor is VS Code",
        "what do you remember about my preferred editor",
        "forget my preferred editor",
    ],
)
def test_explicit_memory_commands_precede_conversation(
    monkeypatch,
    command,
):
    handled = []

    def dynamic_command(text):
        handled.append(text)
        return True

    def unexpected(*args, **kwargs):
        pytest.fail(
            "Explicit memory command must not reach conversation AI"
        )

    monkeypatch.setattr(
        router,
        "process_dynamic_command",
        dynamic_command,
    )
    monkeypatch.setattr(
        router,
        "process_streaming_conversation",
        unexpected,
    )
    monkeypatch.setattr(
        router,
        "ask_ai",
        unexpected,
    )

    router.process(command)

    assert len(handled) == 1

def test_memory_subject_does_not_imply_memory_action(
    monkeypatch,
):
    command = "how does human memory work?"
    checked = []
    heard = []

    def dynamic_command(text):
        checked.append(text)
        return False

    monkeypatch.setattr(
        router,
        "process_dynamic_command",
        dynamic_command,
    )
    monkeypatch.setattr(
        router,
        "process_streaming_conversation",
        lambda text: heard.append(text),
    )

    router.process(command)

    assert checked == ["how does human memory work"]
    assert heard == ["how does human memory work"]