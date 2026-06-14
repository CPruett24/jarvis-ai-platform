from services.speaker import speak
import subprocess
from datetime import datetime
import webbrowser

def process(command):
    command = command.lower()
    
    if command == "hello":
        speak("Hello Chandler")

    elif command == "open vscode":
        speak("Opening Visual Studio Code")
        subprocess.run(["code"], shell=True)

    elif command == "what time is it":
        now = datetime.now().strftime("%I:%M %p")
        speak(f"The current time is {now}")

    elif command == "open github":
        speak("Opening GitHub")
        webbrowser.open("https://github.com")

    else:
        speak("Sorry I don't know how to do that yet.")