import speech_recognition as sr

recognizer = sr.Recognizer()


def listen():
    with sr.Microphone() as source:
        print("Listening...")

        recognizer.adjust_for_ambient_noise(source, duration=1)

        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio)

        print(f"You said: {command}")

        return command.lower()

    except sr.UnknownValueError:
        return ""

    except sr.RequestError:
        return "speech service unavailable"