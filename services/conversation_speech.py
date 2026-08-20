import queue
import threading

from services.sentence_buffer import SentenceBuffer
from services.speaker import speak


class ConversationSpeech:
    """
    Converts streaming AI text into complete sentences
    and speaks them through a background worker.

    The AI streaming loop does not wait for TTS to finish.
    """

    def __init__(
        self,
        speak_function=speak,
    ):
        self.buffer = SentenceBuffer()

        self.speak_function = (
            speak_function
        )

        self.speech_queue = queue.Queue()

        self.worker = threading.Thread(
            target=self._speech_worker,
            daemon=True,
        )

        self.worker.start()

    def _speech_worker(self):

        while True:

            sentence = (
                self.speech_queue.get()
            )

            try:

                if sentence is None:
                    return

                self.speak_function(
                    sentence
                )

            finally:

                self.speech_queue.task_done()

    def add_chunk(self, text):

        sentences = self.buffer.add(
            text
        )

        for sentence in sentences:

            self.speech_queue.put(
                sentence
            )

        return sentences

    def finish(self):

        sentences = self.buffer.flush()

        for sentence in sentences:

            self.speech_queue.put(
                sentence
            )

        return sentences

    def wait_until_finished(self):

        self.speech_queue.join()

    def stop(self):

        self.speech_queue.put(
            None
        )