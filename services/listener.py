import speech_recognition as sr
from services.microphone_service import create_microphone
from services.transcription_service import transcribe_audio
from services.voice_diagnostics import voice_trace
import threading
import time
from dataclasses import dataclass

recognizer = sr.Recognizer()

recognizer.pause_threshold = 1.2
recognizer.non_speaking_duration = 0.8
recognizer.phrase_threshold = 0.3

microphone = create_microphone()

capture_lock = threading.Lock()

WAKE_WORDS = ["jarvis", "hey jarvis"]


def calibrate_microphone():
    print("Calibrating microphone...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        recognizer.dynamic_energy_threshold = True

    print("Calibration complete.\n")


@dataclass(frozen=True)
class SpeechListenResult:
    text: str = ""
    timed_out: bool = False


def listen_for_speech():
    """Compatibility interface for wake-word and other string consumers."""
    return listen_for_speech_result().text


def listen_for_speech_result():
    # A timed-out monitor may still be releasing its capture. Never open a
    # second input stream or classify this resource contention as inactivity.
    if not capture_lock.acquire(timeout=0.25):
        return SpeechListenResult()
    try:
        return _listen_for_speech_result()
    finally:
        capture_lock.release()


def _listen_for_speech_result():
    """Distinguish no captured utterance from captured but unrecognized audio."""
    with microphone as source:

        try:
            listen_started = time.perf_counter()

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=10,
            )

            audio_captured = time.perf_counter()

        except sr.WaitTimeoutError:
            return SpeechListenResult(timed_out=True)

    try:
        transcription_started = time.perf_counter()

        command = transcribe_audio(audio)

        transcription_finished = time.perf_counter()

        capture_time = (
            audio_captured - listen_started
        )

        audio_duration = (
            len(audio.frame_data)
            / (
                audio.sample_rate
                * audio.sample_width
            )
        )

        wait_time = max(
            0.0,
            capture_time - audio_duration,
        )

        transcription_time = (
            transcription_finished
            - transcription_started
        )

        print(
            "[Voice timing] "
            f"wait={wait_time:.2f}s "
            f"audio={audio_duration:.2f}s "
            f"capture={capture_time:.2f}s "
            f"transcription={transcription_time:.2f}s"
        )

        print(f"You: {command}")

        return SpeechListenResult(text=command.lower().strip())

    except sr.UnknownValueError:
        return SpeechListenResult()
    
def listen_for_wake_word():
    speech = listen_for_speech()

    if speech == "":
        return False

    if speech == "exit":
        return "exit"

    return any(wake_word in speech for wake_word in WAKE_WORDS)

class SpeechInterruptMonitor:
    """
    Monitors the microphone while JARVIS is speaking.

    If the user starts speaking, the supplied callback
    is triggered so the current speech can be interrupted.
    """

    _owner_lock = threading.Lock()
    _active_thread = None

    def __init__(self, on_speech):
        self.on_speech = on_speech

        self.microphone = create_microphone()

        self.running = False

        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None

    def _callback(
        self,
        recognizer_instance,
        audio,
    ):
        if not self.running:
            return

        try:
            text = transcribe_audio(audio, interruption=True)

        except Exception as exc:

            print(
                "[Interrupt monitor] "
                f"Transcription failed: {exc}"
            )

            return

        text = text.strip()

        if not self.running:
            return

        if not text:
            return

        print(
            f"[Interrupt monitor] You: {text}"
        )

        self.on_speech(text)

    def _listen(self):
        try:
            while not self.stop_event.is_set():
                if not capture_lock.acquire(timeout=0.1):
                    continue
                try:
                    if self.stop_event.is_set():
                        break
                    with self.microphone as source:
                        try:
                            audio = recognizer.listen(source, timeout=0.25, phrase_time_limit=3)
                        except sr.WaitTimeoutError:
                            continue
                finally:
                    capture_lock.release()
                # Release the input stream before potentially slow inference.
                if self.running:
                    self._callback(recognizer, audio)
        except Exception as error:
            print(f"[Voice] Interruption capture failed ({type(error).__name__}).")
            voice_trace("monitor_failed", error=type(error).__name__)
        finally:
            voice_trace("monitor_thread_exit")

    def start(self):
        with self.lock, type(self)._owner_lock:
            if self.running:
                return
            previous = type(self)._active_thread
            if previous and previous.is_alive():
                print("[Voice] Interruption capture is still recovering.")
                voice_trace("monitor_start_deferred", reason="previous_worker_pending")
                return
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._listen, name="jarvis-microphone", daemon=True)
            type(self)._active_thread = self.thread
            self.thread.start()

    def stop(self, timeout=4.0):
        voice_trace("monitor_shutdown_requested")
        with self.lock:
            self.stop_event.set()
            thread = self.thread
        # In-flight transcription may supply one final handoff during this bound.
        if thread and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        self.running = False
        voice_trace("monitor_shutdown", complete=not thread or not thread.is_alive())
        return not thread or not thread.is_alive()
