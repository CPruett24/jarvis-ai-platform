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
}

def process(command):
    command = command.lower()

    command = command.strip(".,!?")

    command = ALIASES.get(command, command)

    if process_dynamic_command(command):
        return
    
    if "workspace" in command:

        workspace_name = (
            command
            .replace("open my", "")
            .replace("open", "")
            .replace("workspace", "")
            .strip()
        )

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
