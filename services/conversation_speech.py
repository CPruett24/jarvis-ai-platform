import queue
import threading

from services.sentence_buffer import SentenceBuffer
from services.speaker import speak, stop_speaking


class ConversationSpeech:
    """
    Converts streaming AI text into complete sentences
    and speaks them through a background worker.

    Speech can be interrupted. When interrupted, queued
    sentences are discarded and the currently speaking
    sentence is stopped.

    The conversation can then be reset and reused.
    """

    def __init__(
        self,
        speak_function=None,
        stop_function=None,
    ):
        self.buffer = SentenceBuffer()

        self.speak_function = (
            speak_function
            if speak_function is not None
            else speak
        )

        self.stop_function = (
            stop_function
            if stop_function is not None
            else stop_speaking
        )

        self.speech_queue = queue.Queue()

        self.interrupted = threading.Event()

        self.worker = threading.Thread(
            target=self._speech_worker,
            daemon=True,
        )

        self.finished = threading.Event()

        self.worker.start()

    def _speech_worker(self):

        while True:

            sentence = self.speech_queue.get()

            try:

                if sentence is None:
                    return

                if self.interrupted.is_set():
                    continue

                self.speak_function(
                    sentence
                )

            finally:

                self.speech_queue.task_done()

    def add_chunk(self, text):

        if self.interrupted.is_set():
            return []

        sentences = self.buffer.add(
            text
        )

        for sentence in sentences:

            if self.interrupted.is_set():
                break

            self.speech_queue.put(
                sentence
            )

        return sentences

    def finish(self):

        self.finished.clear()

        if self.interrupted.is_set():
            return []

        sentences = self.buffer.flush()

        for sentence in sentences:

            self.speech_queue.put(
                sentence
            )

        self.finished.set()

        return sentences

    def is_finished(self):
        return (
            self.finished.is_set()
            and self.speech_queue.unfinished_tasks == 0
        )

    def interrupt(self):
        """
        Immediately stop the current sentence and discard
        anything waiting in the speech queue.
        """

        self.interrupted.set()

        self.stop_function()

        self.buffer.flush()

        self._clear_queue()

    def is_interrupted(self):
        """
        Return True when the current response has been
        interrupted and should no longer produce speech.
        """

        return self.interrupted.is_set()

    def reset(self):
        """
        Reset the speech pipeline so it can be reused
        for a new response after an interruption.
        """

        self._clear_queue()

        self.buffer.flush()

        self.interrupted.clear()

    def _clear_queue(self):

        while True:

            try:

                self.speech_queue.get_nowait()

            except queue.Empty:

                break

            else:

                self.speech_queue.task_done()

    def wait_until_finished(self):

        self.speech_queue.join()

    def stop(self):

        self.interrupted.set()

        self.stop_function()

        self.buffer.flush()

        self._clear_queue()

        self.speech_queue.put(
            None
        )