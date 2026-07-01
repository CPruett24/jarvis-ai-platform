from services.conversation_manager import debug_topic, set_topic
from services.speaker import speak
import subprocess
from datetime import datetime
import webbrowser
from services.memory_service import remember, get_memories, search_memories, delete_memory
from services.workspace_service import open_workspace
from pathlib import Path
import os
import platform
import sys
import subprocess
from services.project_service import summarize_file, search_project
from services.project_service import get_file_content

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

def project_tree():

    root = Path.cwd()

    speak(f"You are currently in the {root.name} project.")

    directories = []
    files = []

    for item in sorted(root.iterdir()):

        if item.name.startswith("."):
            continue

        if item.is_dir():
            directories.append(item.name)

        else:
            files.append(item.name)

    speak(
        f"I found {len(directories)} folders and {len(files)} files."
    )

    print("\n===== PROJECT STRUCTURE =====")

    print(f"{root.name}/")

    for directory in directories:
        print(f"  📁 {directory}/")

    for file in files:
        print(f"  📄 {file}")

    print("=============================\n")

def find_file(filename=None):

    if not filename:

        speak("Please specify a filename.")

        return

    root = Path.cwd()

    matches = []

    for path in root.rglob("*"):

        if path.name.lower() == filename.lower():

            matches.append(path)

    if not matches:

        speak(f"I couldn't find {filename}.")

        return

    speak(
        f"I found {len(matches)} matching file."
        if len(matches) == 1
        else f"I found {len(matches)} matching files."
    )

    print("\n===== SEARCH RESULTS =====")

    for match in matches:
        print(match.relative_to(root))

    print("==========================\n")

def summarize_file_action(filename=None):

    if not filename:

        speak("Please specify a filename.")

        return

    summary = summarize_file(filename)

    if summary is None:

        speak(f"I couldn't find {filename}.")

        return

    suffix = ""

    if summary["classes"] == 1:
        suffix = "class"
    else:
        suffix = "classes"

    speak(
        f"{filename} contains "
        f"{summary['lines']} lines, "
        f"{summary['functions']} functions, "
        f"and {summary['classes']} {suffix}."
    )

    print("\n===== FILE SUMMARY =====")

    print(f"File: {summary['path']}")

    print(f"Lines: {summary['lines']}")

    print(f"Imports: {summary['imports']}")

    print(f"Functions: {summary['functions']}")

    print(f"Classes: {summary['classes']}")

    print("========================\n")

def search_project_action(keyword=None):

    if not keyword:

        speak("Please specify something to search for.")

        return

    results = search_project(keyword)

    if not results:

        speak(
            f"I couldn't find '{keyword}' anywhere in the project."
        )

        return

    speak(
        f"I found {len(results)} matching files."
    )

    print("\n===== SEARCH RESULTS =====")

    root = Path.cwd()

    for result in results:

        print(result.relative_to(root))

    print("==========================\n")

def explain_file_action(filename=None, depth=1,):

    if not filename:
        speak("Please specify a filename.")
        return

    file_info = get_file_content(filename)

    if file_info is None:
        speak(f"I couldn't find {filename}.")
        return

    speak(f"Analyzing {filename}.")

    from services.ai_service import explain_code
    from services.conversation_manager import set_topic

    explanation = explain_code(file_info, depth)

    set_topic(
        {
            "type": "file",
            "filename": filename,
            "depth": depth,
        }
    )

    print("\n===== CODE EXPLANATION =====\n")
    print(explanation)
    print("\n============================\n")

    speak(explanation)

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