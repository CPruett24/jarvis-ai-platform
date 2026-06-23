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

    for action in workspace.get("actions", []):

        if action == "vscode":
            subprocess.run(["code"], shell=True)

    for url in workspace.get("urls", []):

        webbrowser.open(url)