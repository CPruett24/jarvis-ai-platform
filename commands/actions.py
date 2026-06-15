from services.speaker import speak
import subprocess
from datetime import datetime
import webbrowser


def hello():
    speak("Hello Chandler")


def open_vscode():
    speak("Opening Visual Studio Code")
    subprocess.run(["code"], shell=True)


def current_time():
    now = datetime.now().strftime("%I:%M %p")
    speak(f"The current time is {now}")


def open_github():
    speak("Opening GitHub")
    webbrowser.open("https://github.com")


def open_chatgpt():
    speak("Opening ChatGPT")
    webbrowser.open("https://chatgpt.com")


def unknown():
    speak("Sorry, I don't know how to do that yet.")