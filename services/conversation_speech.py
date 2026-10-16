import queue
import threading
import uuid

from services.sentence_buffer import SentenceBuffer
from services.speaker import speak, stop_speaking

import time
from services.voice_diagnostics import voice_trace
from services.tts.outcome import PlaybackOutcome, playback_outcome

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

        self.response_started_at = None
        self.first_phrase_reported = False

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
        self.bounded_stop = stop_function is None

        self.speech_queue = queue.Queue()

        self.interrupted = threading.Event()
        self.lifecycle_lock = threading.RLock()
        self.closed = False
        self.stop_worker = None
        self.progress_lock = threading.Lock()
        self.last_success_at = None
        self.playback_started_at = None
        self.utterance_id = 0
        self.response_id = uuid.uuid4().hex[:8]
        self.results = []
        self.terminal_outcome = None

        self.worker = threading.Thread(
            target=self._speech_worker,
            name="jarvis-speech",
            daemon=True,
        )

        self.finished = threading.Event()

        self.worker.start()

    def start_response(self):
        """
        Start timing a new streamed speech response.
        """

        self.response_started_at = time.perf_counter()
        self.first_phrase_reported = False

    def _speech_worker(self):

        while True:

            item = self.speech_queue.get()

            try:

                if item is None:
                    return
                utterance_id, sentence = item

                if self.interrupted.is_set():
                    voice_trace("utterance_result", utterance=utterance_id, outcome="skipped",
                                pending=self.speech_queue.unfinished_tasks)
                    continue

                with self.progress_lock:
                    if self.playback_started_at is None:
                        self.playback_started_at = time.monotonic()
                voice_trace("utterance_start", utterance=utterance_id,
                            pending=self.speech_queue.unfinished_tasks)
                try:
                    result = playback_outcome(self.speak_function(sentence))
                except Exception as error:
                    print(f"[TTS] Speech worker failed ({type(error).__name__}).")
                    result = PlaybackOutcome.FAILED
                with self.progress_lock:
                    # A late provider return after cancellation cannot prove completion.
                    if self.interrupted.is_set():
                        result = PlaybackOutcome.INTERRUPTED
                    self.results.append(result)
                    if result == PlaybackOutcome.COMPLETED:
                        self.last_success_at = time.monotonic()
                voice_trace("utterance_result", utterance=utterance_id, outcome=result.value,
                            progress=self.last_success_at,
                            pending=self.speech_queue.unfinished_tasks)

            except Exception as error:
                # A failed sentence must not kill the worker or strand the queue.
                print(f"[TTS] Speech worker failed ({type(error).__name__}).")

            finally:

                self.speech_queue.task_done()

    def add_chunk(self, text):
        with self.lifecycle_lock:
            if self.closed:
                return []
            return self._add_chunk(text)

    def _add_chunk(self, text):

        if self.interrupted.is_set():
            return []

        sentences = self.buffer.add(
            text
        )

        if (
            sentences
            and not self.first_phrase_reported
            and self.response_started_at is not None
        ):
            self.first_phrase_reported = True

            print(
                "[Voice timing] "
                "first_speakable_phrase="
                f"{time.perf_counter() - self.response_started_at:.2f}s"
            )

        for sentence in sentences:

            if self.interrupted.is_set():
                break

            self._enqueue(sentence)

        return sentences

    def finish(self):
        with self.lifecycle_lock:
            if self.closed:
                return []
            return self._finish()

    def _finish(self):

        self.finished.clear()

        if self.interrupted.is_set():
            return []

        sentences = self.buffer.flush()

        for sentence in sentences:

            self._enqueue(sentence)

        self.finished.set()

        return sentences

    def _enqueue(self, sentence):
        self.utterance_id += 1
        identifier = f"{self.response_id}:{self.utterance_id}"
        self.speech_queue.put((identifier, sentence))
        voice_trace("utterance_queued", utterance=identifier,
                    pending=self.speech_queue.unfinished_tasks)

    def is_finished(self):
        return (
            self.finished.is_set()
            and self.speech_queue.unfinished_tasks == 0
        )

    def progress_timestamp(self):
        with self.progress_lock:
            return self.last_success_at or self.playback_started_at

    def playback_outcome(self):
        with self.progress_lock:
            if self.terminal_outcome is not None:
                return self.terminal_outcome
            if PlaybackOutcome.TIMED_OUT in self.results:
                return PlaybackOutcome.TIMED_OUT
            if any(result in (PlaybackOutcome.FAILED, PlaybackOutcome.SKIPPED)
                   for result in self.results):
                return PlaybackOutcome.FAILED
            if PlaybackOutcome.INTERRUPTED in self.results:
                return PlaybackOutcome.INTERRUPTED
            if self.is_finished() and self.results and all(
                    result == PlaybackOutcome.COMPLETED for result in self.results):
                return PlaybackOutcome.COMPLETED
            return PlaybackOutcome.UNKNOWN

    def mark_timeout(self):
        with self.progress_lock:
            self.terminal_outcome = PlaybackOutcome.TIMED_OUT
        voice_trace("playback_timeout", reason="no_successful_utterance_progress",
                    pending=self.speech_queue.unfinished_tasks)
        self.interrupt()

    def interrupt(self):
        """
        Immediately stop the current sentence and discard
        anything waiting in the speech queue.
        """

        with self.lifecycle_lock:
            if self.interrupted.is_set():
                return
            with self.progress_lock:
                if self.terminal_outcome is None:
                    self.terminal_outcome = PlaybackOutcome.INTERRUPTED
            self.interrupted.set()
            self.buffer.flush()
            self._clear_queue()
            if self.bounded_stop:
                # The shared speaker already owns a bounded stop worker. Make
                # its request before another response can begin playback.
                self._request_stop()
            else:
                self.stop_worker = threading.Thread(
                    target=self._request_stop, name="jarvis-speech-stop", daemon=True,
                )
                self.stop_worker.start()
        if self.stop_worker:
            self.stop_worker.join(timeout=0.02)

    def _request_stop(self):
        voice_trace("speech_cancel_request")
        try:
            self.stop_function()
        except Exception as error:
            print(f"[TTS] Stop failed ({type(error).__name__}).")
        finally:
            voice_trace("speech_cancel_complete")

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

        if self.closed or (self.stop_worker and self.stop_worker.is_alive()):
            raise RuntimeError("Speech is closed or cancellation is still pending")
        self._clear_queue()

        self.buffer.flush()

        self.interrupted.clear()
        with self.progress_lock:
            self.last_success_at = self.playback_started_at = None
            self.results.clear()
            self.terminal_outcome = None

    def _clear_queue(self):

        while True:

            try:

                item = self.speech_queue.get_nowait()

            except queue.Empty:

                break

            else:
                if item is not None:
                    voice_trace("utterance_result", utterance=item[0], outcome="skipped",
                                pending=self.speech_queue.unfinished_tasks)
                self.speech_queue.task_done()

    def wait_until_finished(self, timeout=5):
        deadline = time.monotonic() + timeout
        while self.speech_queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.01)
        return self.speech_queue.unfinished_tasks == 0

    def stop(self, timeout=0.25):
        with self.lifecycle_lock:
            if self.closed:
                return not self.worker.is_alive()
            self.closed = True
            # A completed response needs no provider cancellation.
            if self.speech_queue.unfinished_tasks:
                self.interrupt()
            self.interrupted.set()
            self._clear_queue()
            self.speech_queue.put(None)
        self.worker.join(timeout=timeout)
        voice_trace("speech_worker_shutdown", complete=not self.worker.is_alive())
        return not self.worker.is_alive()
