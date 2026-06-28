import speech_recognition as sr
from services.transcription_service import transcribe_audio

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