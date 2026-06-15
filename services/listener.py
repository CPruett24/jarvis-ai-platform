import speech_recognition as sr

recognizer = sr.Recognizer()
microphone = sr.Microphone(device_index=1)

WAKE_WORDS = ["jarvis", "hey jarvis"]


def calibrate_microphone():
    print("Calibrating microphone...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

    print("Calibration complete.\n")


def listen_for_speech():
    with microphone as source:

        try:
            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=5
            )

        except sr.WaitTimeoutError:
            return ""

    try:
        command = recognizer.recognize_google(audio)

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