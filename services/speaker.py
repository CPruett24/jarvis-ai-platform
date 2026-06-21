import pyttsx3

from services.status_service import (
    update_status,
    update_last_response,
)


def speak(text):

    print(f"JARVIS: {text}")

    update_status("speaking")
    update_last_response(text)

    engine = pyttsx3.init()

    engine.say(text)
    engine.runAndWait()

    engine.stop()

    update_status("listening")