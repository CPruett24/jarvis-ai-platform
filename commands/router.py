from services.ai_service import ask_ai, detect_tool
from services.speaker import speak
from services.workspace_service import open_workspace
from commands.static_commands import COMMANDS
from commands.dynamic_commands import process_dynamic_command
from commands.tool_manager import execute_tool

ALIASES = {
    "open chat gpt": "open chatgpt",
    "open chat g p t": "open chatgpt",
    "what's the time": "what time is it",
    "tell me the time": "what time is it",
    "hi": "hello",
    "hey": "hello",
    "what's the time": "what time is it",
    "tell me the time": "what time is it",
    "what time is it right now": "what time is it",
    "can you tell me the time": "what time is it",
    "where are we": "where am i",
    "what folder am i in": "where am i",
    "show files": "list files",
    "show me the files": "list files",
    "computer information": "tell me about this computer",
    "system information": "tell me about this computer",
    "current branch": "what branch am i on",
    "repository status": "git status",
    "repo status": "git status",
    "python version": "what version of python am i running",
    "current project": "what project am i in",
}

def process(command):
    command = command.lower()

    command = command.strip(".,!?")

    command = ALIASES.get(command, command)

    if process_dynamic_command(command):
        return
    
    if "workspace" in command:

        workspace_name = None

        if "coding" in command:
            workspace_name = "coding"

        elif "aws" in command:
            workspace_name = "aws"

        elif "school" in command:
            workspace_name = "school"

        if workspace_name:

            print(f"Workspace requested: {workspace_name}")

            execute_tool(f"open_{workspace_name}_workspace")

            return

    tool_name = COMMANDS.get(command)

    if tool_name:
        execute_tool(tool_name)
        return

    tool = detect_tool(command)

    print(f"Selected tool: {tool}")

    if tool != "none":

        tool_names = [
            t.strip()
            for t in tool.split(",")
        ]

        for tool_name in tool_names:

            execute_tool(tool_name)

        return
    
    print("Calling ask_ai...")

    response = ask_ai(command)

    print("AI returned:", response)

    print("Speaking...")

    speak(response)
