from services.listener import (
    calibrate_microphone,
    listen_for_speech,
    listen_for_wake_word,
)
from services.status_service import (
    update_last_command,
    update_status,
)

from commands.router import process
from services.speaker import speak

SESSION_END_PHRASES = [
    "that's all",
    "thank you",
    "thanks",
    "goodbye",
    "never mind",
    "nevermind",
    "i'm done",
    "im done",
]

speak("JARVIS online.")

update_status("listening")

calibrate_microphone()

print('Waiting for "Jarvis"...')

while True:

    wake_result = listen_for_wake_word()

    if wake_result == "exit":
        speak("Goodbye Chandler.")
        break

    if wake_result:

        speak("Yes, Chandler?")

        while True:

            command = listen_for_speech()

            update_last_command(command)

            if command == "":
                speak("Returning to standby.")
                break

            command = command.lower().strip(".,!?")

            print(f"Session command: '{command}'")

            if command == "exit":
                speak("Goodbye Chandler.")
                exit()

            if any(
                phrase in command
                for phrase in SESSION_END_PHRASES
            ):
                speak("Anytime.")
                break

            process(command)

        print('\nWaiting for "Jarvis"...')