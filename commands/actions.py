from services.conversation_manager import debug_topic, set_topic
from services.speaker import speak
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
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
from services.conversation_manager import set_pending_request
from services.project_service import get_file_content, find_matching_files
from models.tool_request import ToolRequest
from services.conversation_manager import set_topic, record_turn, clear_context


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

            return {
                "response": (
                    f"You are currently on the {branch} branch."
                ),
                "observations": {
                    "git_branch": branch,
                },
            }

        else:

            return {
                "response": "I couldn't determine the current branch.",
                "observations": {
                    "git_branch": None,
                },
            }

    except Exception:

        return {
            "response": "This folder is not a Git repository.",
            "observations": {
                "git_repository": False,
            },
        }

def git_status():

    try:

        status = subprocess.check_output(
            ["git", "status", "--short"],
            text=True
        ).strip()

        if not status:

            return {
                "response": "Your repository is clean.",
                "observations": {
                    "git_status": "clean",
                    "modified_or_untracked_files": 0,
                },
            }

        modified_files = len(status.splitlines())

        return {
            "response": (
                f"You have {modified_files} modified or untracked files."
            ),
            "observations": {
                "git_status": status,
                "modified_or_untracked_files": modified_files,
            },
        }

    except Exception:

        return {
            "response": "This folder is not a Git repository.",
            "observations": {
                "git_repository": False,
            },
        }

def git_remote():

    try:

        remotes = subprocess.check_output(
            ["git", "remote"],
            text=True
        ).splitlines()

        if not remotes:

            return {
                "response": "No Git remotes are configured.",
                "observations": {
                    "git_remotes": [],
                },
            }

        return {
            "response": (
                "Your configured Git remotes are: "
                + ", ".join(remotes)
            ),
            "observations": {
                "git_remotes": remotes,
            },
        }

    except Exception:

        return {
            "response": "This folder is not a Git repository.",
            "observations": {
                "git_repository": False,
            },
        }

def python_version():

    version = sys.version.split()[0]

    spoken_version = version.replace(".", " point ")

    speak(
        f"You are running Python version {spoken_version}."
    )

def project_tree():

    root = Path.cwd()

    directories = []
    files = []

    for item in sorted(root.iterdir()):

        if item.name.startswith("."):
            continue

        if item.is_dir():
            directories.append(item.name)

        else:
            files.append(item.name)

    print("\n===== PROJECT STRUCTURE =====")

    print(f"{root.name}/")

    for directory in directories:
        print(f"  📁 {directory}/")

    for file in files:
        print(f"  📄 {file}")

    print("=============================\n")

    return {
        "response": (
            f"You are currently in the {root.name} project. "
            f"I found {len(directories)} folders and {len(files)} files."
        ),
        "observations": {
            "project": root.name,
            "folder_count": len(directories),
            "file_count": len(files),
        },
    }

def find_file(filename=None):

    if not filename:

        return {
            "response": "Please specify a filename.",
            "observations": {},
        }

    root = Path.cwd()

    matches = []

    for path in root.rglob("*"):

        if path.name.lower() == filename.lower():

            matches.append(path)

    if not matches:

        return {
            "response": f"I couldn't find {filename}.",
            "observations": {
                "file_search": filename,
                "matches": [],
            },
        }

    print("\n===== SEARCH RESULTS =====")

    for match in matches:
        print(match.relative_to(root))

    print("==========================\n")

    relative_matches = [
        str(match.relative_to(root))
        for match in matches
    ]

    return {
        "response": (
            f"I found {len(matches)} matching file."
            if len(matches) == 1
            else f"I found {len(matches)} matching files."
        ),
        "observations": {
            "file_search": filename,
            "matches": relative_matches,
        },
    }

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

        return {
            "response": "Please specify something to search for.",
            "observations": {},
        }

    results = search_project(keyword)

    if not results:

        return {
            "response": (
                f"I couldn't find '{keyword}' anywhere in the project."
            ),
            "observations": {
                "project_search": keyword,
                "matches": [],
            },
        }

    print("\n===== SEARCH RESULTS =====")

    root = Path.cwd()

    for result in results:

        print(result.relative_to(root))

    print("==========================\n")

    relative_results = [
        str(result.relative_to(root))
        for result in results
    ]

    return {
        "response": f"I found {len(results)} matching files.",
        "observations": {
            "project_search": keyword,
            "matches": relative_results,
        },
    }

def explain_file_action(filename=None, depth=1,):

    if not filename:

        set_pending_request(
            {
                "request": ToolRequest(
                    tool="explain_file",
                    arguments={}
                ),
                "missing": "filename",
                "candidates": None,
                "prompt": (
                    "Sure. Which file would you like me to explain?"
                ),
            }
        )

        speak("Sure. Which file would you like me to explain?")

        return

    matches = find_matching_files(filename)

    if len(matches) > 1:

        names = ", ".join(
            path.name
            for path in matches
        )

        set_pending_request(
            {
                "request": ToolRequest(
                    tool="explain_file",
                    arguments={}
                ),
                "missing": "filename",
                "candidates": matches,
                "prompt": (
                    f"I found multiple matching files: {names}. "
                    "Which one would you like me to explain?"
                ),
            }
        )

        names = ", ".join(
            path.name
            for path in matches
        )

        speak(
            f"I found multiple matching files: {names}. "
            "Which one would you like me to explain?"
        )

        return

    if not matches:

        speak(
            f"I couldn't find a file named {filename}. "
            "Could you try another name?"
        )

        return

    file_info = get_file_content(filename)

    speak(f"Analyzing {filename}.")

    from services.ai_service import explain_code

    explanation = explain_code(file_info, depth)

    clear_context()

    set_topic(
        {
            "type": "file",
            "filename": filename,
            "depth": depth,
        }
    )

    record_turn(
        "user",
        f"Explain {filename}",
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
    now = datetime.now(
        ZoneInfo("America/New_York")
    ).strftime("%I:%M %p")

    return {
        "response": f"The current time is {now}",
        "observations": {
            "current_time": now,
            "timezone": "America/New_York",
        },
    }

def open_github():
    speak("Opening GitHub")
    webbrowser.open("https://github.com")


def open_chatgpt():
    speak("Opening ChatGPT")
    webbrowser.open("https://chatgpt.com")


def unknown():
    speak("Sorry, I don't know how to do that yet.")
