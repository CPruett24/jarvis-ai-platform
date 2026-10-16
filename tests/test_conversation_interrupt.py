from services.conversation_interrupt import (
    ConversationInterruptController,
)


class FakeSpeech:

    def __init__(self):
        self.interrupted = False

    def interrupt(self):
        self.interrupted = True


def test_interrupt_controller_signals_without_native_stop():

    speech = FakeSpeech()

    controller = ConversationInterruptController(
        speech
    )

    controller.handle_speech(
        "wait jarvis"
    )

    assert speech.interrupted is False

    assert controller.was_interrupted() is True

    assert (
        controller.get_interrupted_text()
        == "wait jarvis"
    )


def test_interrupt_controller_ignores_empty_text():

    speech = FakeSpeech()

    controller = ConversationInterruptController(
        speech
    )

    controller.handle_speech("")

    assert speech.interrupted is False

    assert controller.was_interrupted() is False

    assert (
        controller.get_interrupted_text()
        is None
    )


def test_interrupt_controller_selects_followup_instead_of_stale_first():

    speech = FakeSpeech()

    controller = ConversationInterruptController(
        speech
    )

    controller.handle_speech(
        "first interruption"
    )

    controller.handle_speech(
        "second interruption"
    )

    assert (
        controller.get_interrupted_text()
        == "second interruption"
    )


def test_interrupt_controller_reset():

    speech = FakeSpeech()

    controller = ConversationInterruptController(
        speech
    )

    controller.handle_speech(
        "stop talking"
    )

    controller.reset()

    assert controller.was_interrupted() is False

    assert (
        controller.get_interrupted_text()
        is None
    )
