from services.listener import (
    calibrate_microphone,
    listen_for_speech,
    listen_for_wake_word,
)
from commands.router import process
from services.speaker import speak

SESSION_END_PHRASES = [
    "that's all",
    "thank you",
    "thanks",
    "goodbye",
]

speak("JARVIS online.")

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

            if command == "":
                speak("Returning to standby.")

                break

            if command == "exit":
                speak("Goodbye Chandler.")

                exit()

            if command in SESSION_END_PHRASES:
                speak("Anytime.")

                break

            process(command)

        print('\nWaiting for "Jarvis"...')