from services.speaker import speak
import subprocess
from datetime import datetime
import webbrowser
from services.memory_service import remember, get_memories, search_memories, delete_memory
from services.workspace_service import open_workspace
import os
import platform
import sys
import subprocess

def remember_command(command):
    memory = command.replace("remember ", "", 1).strip()

    remember(memory)
    speak("Got that stored Chandler.")

def recall_memories():
    memories = get_memories()
    if not memories:
        speak("I don't remember anything yet.")
        return

    speak("Here's what I remember:")
    for memory in memories:
        speak(memory.content)

def search_memory_command(command):
    keyword = (command.replace("what do you remember about", "",).strip())

    print(f"Keyword: {keyword}")

    memories = search_memories(keyword)
    if not memories:
        speak(f"I don't remember anything about {keyword}.")
        return
    
    speak(f"Here's what I remember about {keyword}:")
    for memory in memories:
        speak(memory.content)

def forget_memory_command(command):
    keyword = (command.replace("forget", "",).strip())

    print(f"DELETE KEYWORD: {keyword}")

    deleted = delete_memory(keyword)

    if deleted:
        speak(f"I've forgotten that.")
    else:
        speak(f"I couldn't find that memory.")

def current_directory():

    directory = os.getcwd()

    speak(f"You are currently in {directory}")

def list_files():

    files = os.listdir()

    if not files:

        speak("The current folder is empty.")

        return

    speak("Here are the files in the current folder.")

    for file in files:

        speak(file)

def system_info():

    operating_system = platform.system()
    python_version = platform.python_version()
    current_directory = os.getcwd()

    speak(
        f"You are running {operating_system}. "
        f"Python version {python_version}. "
        f"The current directory is {current_directory}."
    )

def current_project():

    project = os.path.basename(os.getcwd())

    speak(
        f"You are currently working in the {project} project."
    )

def git_branch():

    try:

        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True
        ).strip()

        if branch:

            speak(
                f"You are currently on the {branch} branch."
            )

        else:

            speak("I couldn't determine the current branch.")

    except Exception:

        speak(
            "This folder is not a Git repository."
        )

def git_status():

    try:

        status = subprocess.check_output(
            ["git", "status", "--short"],
            text=True
        ).strip()

        if not status:

            speak(
                "Your repository is clean."
            )

            return

        modified_files = len(status.splitlines())

        speak(
            f"You have {modified_files} modified or untracked files."
        )

    except Exception:

        speak(
            "This folder is not a Git repository."
        )

def git_remote():

    try:

        remotes = subprocess.check_output(
            ["git", "remote"],
            text=True
        ).splitlines()

        if not remotes:

            speak(
                "No Git remotes are configured."
            )

            return

        speak(
            "Your configured Git remotes are:"
        )

        for remote in remotes:

            speak(remote)

    except Exception:

        speak(
            "This folder is not a Git repository."
        )

def python_version():

    version = sys.version.split()[0]

    spoken_version = version.replace(".", " point ")

    speak(
        f"You are running Python version {spoken_version}."
    )

def open_coding_workspace(workspace="coding"):
    open_workspace(workspace)

def open_aws_workspace(workspace="aws"):
    open_workspace(workspace)

def open_school_workspace(workspace="school"):
    open_workspace(workspace)

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