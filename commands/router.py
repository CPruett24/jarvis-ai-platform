from services.ai_service import ask_ai, detect_tool
from services.speaker import speak
from services.workspace_service import open_workspace
from commands.static_commands import COMMANDS
from commands.dynamic_commands import process_dynamic_command
from commands.tool_manager import execute_tool
from models.tool_request import ToolRequest
from services.command_parser import parse_command
from services.conversation_manager import (
    has_pending_request,
    complete_pending_request,
    is_follow_up,
    resolve_follow_up,
    is_topic_switch,
    resolve_topic_switch,
)
from services.code_intent import (
    is_code_question,
    is_contextual_code_question,
)
from services.conversation_manager import get_topic, get_conversation_context, record_turn
from services.project_service import get_file_content
from services.code_assistant import answer_question


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

    if has_pending_request():

        pending = complete_pending_request(
            filename=command
        )

        if pending:

            execute_tool(pending)

            return
        
    if is_topic_switch(command):

        switch = resolve_topic_switch(command)

        if switch:

            execute_tool(switch)

            return

    parsed = parse_command(command)

    #
    # Conversational Code Reasoning
    #

    topic = get_topic()

    if topic and (
        is_code_question(command)
        or is_contextual_code_question(command)
    ):

        file_info = get_file_content(
            topic["filename"]
        )

        if file_info:

            print("[Router] Code discussion detected.")

            record_turn(
                "user",
                command,
            )

            context = get_conversation_context()

            response = answer_question(
                command,
                file_info,
                context,
            )

            record_turn(
                "assistant",
                response,
            )

            speak(response)

            return

    if is_follow_up(command):

        follow_up = resolve_follow_up(command)

        if follow_up:

            execute_tool(follow_up)

            return

    if parsed:

        execute_tool(parsed)

        return

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
