import json
import subprocess
import webbrowser

from services.speaker import speak

WORKSPACE_FILE = "data/workspaces.json"

def load_workspaces():

    with open(WORKSPACE_FILE, "r") as file:
        return json.load(file)
    
def open_workspace(name):

    workspaces = load_workspaces()

    workspace = workspaces.get(name)

    if not workspace:

        speak("I couldn't find that workspace.")

        return

    speak(workspace["speak"])

    for action in workspace["actions"]:

        if action == "vscode":
            subprocess.run(["code"], shell=True)

        elif action == "github":
            webbrowser.open("https://github.com")

        elif action == "chatgpt":
            webbrowser.open("https://chatgpt.com")

        elif action == "aws_console":
            webbrowser.open("https://console.aws.amazon.com")

        elif action == "canvas":
            webbrowser.open("https://canvas.fau.edu/")

        elif action == "school_email": 
            webbrowser.open("https://outlook.office.com/mail/?realm=fau.edu&vd=outlook")

        elif action == "school_portal":
            webbrowser.open("https://myfau.fau.edu/u/myfau/index")