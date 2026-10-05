from services.listener import (
    calibrate_microphone,
    listen_for_speech_result,
    listen_for_wake_word,
)

from services.transcription_service import (
    warm_up_transcription,
)

from services.status_service import (
    update_last_command,
    update_status,
)

from services.conversation_db import (
    start_session,
    end_session,
)

from services.conversation_service import (
    restore_recent_history,
)

from commands.router import process
from services.ai_service import warm_up_ai
from services.speaker import speak
from models.session import Session
from models.conversation import Conversation
from models.memory import initialize_database

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

initialize_database()

restore_recent_history()

start_session()

speak("JARVIS online.")

update_status("listening")

calibrate_microphone()

print("Warming up speech recognition...")
warm_up_transcription()

print("Warming up conversational AI...")
warm_up_ai()

print('Waiting for "Jarvis"...')

while True:

    wake_result = listen_for_wake_word()

    if wake_result == "exit":

        end_session()

        speak("Goodbye Chandler.")

        break

    if wake_result:

        speak("Yes, Chandler?")

        while True:

            listen_result = listen_for_speech_result()

            if listen_result.timed_out:
                speak("Returning to standby.")
                break

            command = listen_result.text
            if not command:
                continue

            update_last_command(command)

            command = command.lower().strip(".,!?")

            print(f"Session command: '{command}'")

            if command == "exit":

                end_session()

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
