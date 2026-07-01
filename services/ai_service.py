import json
from models.tool_request import ToolRequest
from ollama import chat
from services.conversation_service import add_message, get_history
from services.memory_service import get_memory_context
from services.status_service import update_status
from commands.tool_manager import get_tool_descriptions

def ask_ai(prompt):

    add_message(
    "user",
    prompt
    )
    update_status("thinking")

    memory_context = get_memory_context()

    print("\nMEMORY CONTEXT:")
    print(memory_context)
    print()

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS, a personal AI assistant created for your user."

                "\n\nYou are speaking directly to the user."

                "\nAlways address the user as 'you' and 'your'."

                "\nDo not refer to the user in the third person."

                "\nDo not call the user 'Chandler'."

                "\nDo not use phrases like 'he', 'him', 'the user', or 'Chandler' when talking about the person you are speaking to."

                "\n\nWhen discussing stored memories, phrase them naturally."

                "\nExample: say 'Your project deadline is Friday.'"

                "\nExample: say 'You told me your project deadline is Friday.'"

                "\nDo not say \"User's name's project deadline is Friday.\""

                "\n\nThe following memories are facts about the person you are speaking to:\n\n"

                f"{memory_context}"
            ),
        }
    ]

    messages.extend(get_history())

    response = chat(
        model="llama3.1:8b",
        messages=messages,
    )

    answer = response["message"]["content"]

    add_message(
    "assistant",
    answer
    )

    return answer

def explain_code(file_info, depth=1,):
    if depth == 1:

        instruction = (
            "Give a high-level overview of the file. "
            "Focus on its overall purpose and responsibilities."
        )

    elif depth == 2:

        instruction = (
            "Assume the developer already understands the overview. "
            "Now explain the important functions and how they work together."
        )

    elif depth == 3:

        instruction = (
            "Walk through how the code executes and how data flows through the file."
        )

    else:

        instruction = (
            "Discuss the architecture, design decisions, strengths, weaknesses, "
            "and possible improvements."
        )

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert senior software engineer.\n\n"

                    "Explain code clearly for the developer.\n"

                    "Do not repeat the code.\n"

                    f"{instruction}\n"

                    "Identify important functions.\n"

                    "Identify responsibilities.\n"

                    "Mention any obvious architectural observations.\n"

                    "Keep the explanation under 250 words."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Filename: {file_info['filename']}\n\n"

                    f"{file_info['content']}"
                ),
            },
        ],
    )

    return response["message"]["content"]

def detect_tool(command):

    tool_descriptions = get_tool_descriptions()

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a tool selector.\n\n"

                    "Your job is to determine which tool should be executed.\n\n"

                    "Only return the tool name.\n\n"

                    "If the user is asking a question, making conversation, or requesting information, return 'none'.\n\n"

                    "If multiple tools are requested, return the tool names separated by commas.\n\n"

                    "Examples:\n\n"

                    "Open GitHub\n"
                    "-> open_github\n\n"

                    "Can you open GitHub for me?\n"
                    "-> open_github\n\n"

                    "Open GitHub and VS Code\n"
                    "-> open_github,open_vscode\n\n"

                    "Open my coding workspace\n"
                    "-> open_coding_workspace\n\n"

                    "Open my AWS workspace\n"
                    "-> open_aws_workspace\n\n"

                    "Open my school workspace\n"
                    "-> open_school_workspace\n\n"

                    "What time is it?\n"
                    "-> current_time\n\n"

                    "Hello\n"
                    "-> hello\n\n"

                    "Remember I like pizza.\n"
                    "-> none\n\n"

                    "How are you?\n"
                    "-> none\n\n"

                    "Available tools:\n\n"

                    f"{tool_descriptions}"

                    "\n\nIf no tool should be executed, return 'none'."
                ),
            },
            {
                "role": "user",
                "content": command,
            },
        ],
    )

    tool = response["message"]["content"].strip().splitlines()[0]

    return tool
