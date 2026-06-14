from services.speaker import speak
import subprocess

def process(command):
    command = command.lower()
    
    if command == "hello":
        speak("Hello Chandler")

    elif command == "open vscode":
        speak("Opening Visual Studio Code")
        subprocess.run(["code"], shell=True)

    else:
        speak("Sorry I don't know how to do that yet.")