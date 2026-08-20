import speech_recognition as sr
from services.transcription_service import transcribe_audio
import threading

recognizer = sr.Recognizer()

recognizer.pause_threshold = 1.2
recognizer.non_speaking_duration = 0.8
recognizer.phrase_threshold = 0.3

microphone = sr.Microphone()

WAKE_WORDS = ["jarvis", "hey jarvis"]


def calibrate_microphone():
    print("Calibrating microphone...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        recognizer.dynamic_energy_threshold = True

    print("Calibration complete.\n")


def listen_for_speech():
    with microphone as source:

        try:
            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=10
            )

        except sr.WaitTimeoutError:
            return ""

    try:
        command = transcribe_audio(audio)

        print(f"You: {command}")

        return command.lower()

    except sr.UnknownValueError:
        return ""

    except sr.RequestError:
        print("Speech recognition service unavailable.")

        return ""
    
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

    def __init__(self, on_speech):
        self.on_speech = on_speech

        self.microphone = sr.Microphone()

        self.stop_listening = None

        self.running = False

        self.lock = threading.Lock()

    def _callback(
        self,
        recognizer_instance,
        audio,
    ):
        if not self.running:
            return

        try:
            text = transcribe_audio(audio)

        except Exception as exc:

            print(
                "[Interrupt monitor] "
                f"Transcription failed: {exc}"
            )

            return

        text = text.strip()

        if not text:
            return

        print(
            f"[Interrupt monitor] You: {text}"
        )

        self.on_speech(text)

    def start(self):
        with self.lock:

            if self.running:
                return

            self.running = True

            self.stop_listening = (
                recognizer.listen_in_background(
                    self.microphone,
                    self._callback,
                    phrase_time_limit=3,
                )
            )

    def stop(self):
        with self.lock:

            if not self.running:
                return

            self.running = False

            stop_function = self.stop_listening
            self.stop_listening = None

        if stop_function:
            stop_function(
                wait_for_stop=True
            )