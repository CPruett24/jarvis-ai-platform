import speech_recognition as sr

recognizer = sr.Recognizer()


def listen():
    with sr.Microphone(device_index=1) as source:
        print("Adjusting for ambient noise...")

        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("Listening...")

        try:
            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=5
            )

            print("Processing speech...")

        except sr.WaitTimeoutError:
            print("No speech detected.")
            return ""

    try:
        command = recognizer.recognize_google(audio)

        print(f"You said: {command}")

        return command.lower()

    except sr.UnknownValueError:
        print("Sorry, I couldn't understand that.")
        return ""

    except sr.RequestError as e:
        print(f"Speech service error: {e}")
        return ""