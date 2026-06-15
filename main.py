from commands.router import process
from services.speaker import speak
from services.listener import listen

speak("Jarvis Online.")

while True:
    command = listen()

    if not command:
        continue

    if command.lower() == "exit":
        print("Shutting down.")
        break

    process(command)