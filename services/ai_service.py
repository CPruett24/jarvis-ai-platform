import json
from models.tool_request import ToolRequest
from ollama import chat
from services.conversation_service import add_message, get_history
from services.memory_service import get_memory_context
from services.status_service import update_status
from commands.tool_manager import get_tool_descriptions
from services.conversation_manager import get_topic
from services.project_service import get_file_content
from services.capability_service import get_capability_context

def ask_ai(
    prompt,
    stream=False,
    on_chunk=None,
):
    add_message(
        "user",
        prompt,
    )

    update_status("thinking")

    memory_context = get_memory_context()

    topic = get_topic()

    capability_context = get_capability_context()

    conversation_context = ""

    if topic:

        if topic["type"] == "file":

            conversation_context = (
                "\n\nCurrent conversation topic:\n"
                f"You are discussing the file "
                f"{topic['filename']}.\n"
                "The user may ask follow-up questions "
                "about this file without naming it again."
            )

    print("\nMEMORY CONTEXT:")
    print(memory_context)
    print()

    code_context = ""

    if topic:

        if topic["type"] == "file":

            file_info = get_file_content(
                topic["filename"]
            )

            if file_info:

                code_context = (
                    "\n\nCurrent file contents:\n\n"
                    f"{file_info['content']}"
                )

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS, a personal AI assistant "
                "created for your user."

                "\n\nYou are speaking directly to the user."

                "\nAlways address the user as 'you' and 'your'."

                "\nDo not refer to the user in the third person."

                "\nDo not call the user 'Chandler'."

                "\nDo not use phrases like 'he', 'him', "
                "'the user', or 'Chandler' when talking "
                "about the person you are speaking to."

                "\n\nWhen discussing stored memories, "
                "phrase them naturally."

                "\nExample: say 'Your project deadline is Friday.'"

                "\nExample: say 'You told me your project "
                "deadline is Friday.'"

                "\nDo not say \"User's name's project "
                "deadline is Friday.\""

                "\n\nThe following memories are facts "
                "about the person you are speaking to:\n\n"

                "\n\nCAPABILITY RULES:\n"
                f"{capability_context}\n"
                "\nNever invent capabilities, actions, access, "
                "information, or results.\n"
                "Never imply that you have information simply "
                "because the user asked about it.\n"
                "If a capability is unavailable, do not infer, "
                "guess, or imply the current state of that system.\n"
                "Do not say that something is empty, unavailable, "
                "completed, scheduled, sent, checked, or found unless "
                "you actually have the data or executed the capability "
                "that establishes that fact.\n"
                "Never claim that you checked a calendar, email, "
                "messages, browser, smart-home device, or other "
                "external system unless a real capability for that "
                "system is available and was actually executed.\n"

                f"{memory_context}"

                f"{conversation_context}"

                f"{code_context}"
            ),
        }
    ]

    messages.extend(
        get_history()
    )

    response = chat(
        model="llama3.1:8b",
        messages=messages,
        stream=stream,
    )

    if not stream:

        answer = response["message"]["content"]

        add_message(
            "assistant",
            answer,
        )

        return answer

    full_response = ""

    for chunk in response:

        text = chunk["message"]["content"]

        if not text:
            continue

        full_response += text

        if on_chunk:

            on_chunk(text)

    add_message(
        "assistant",
        full_response,
    )

    return full_response

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

def explain_impact(
    command,
    impact_data,
):
    """
    Explain verified project impact data using AI.

    The AI is given project-analysis facts and should
    reason about their engineering significance without
    inventing project relationships.
    """

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are JARVIS, an expert senior software engineer.\n\n"

                    "You are analyzing verified static project-analysis data.\n\n"

                    "The project-analysis system has already determined "
                    "the relationships shown below.\n\n"

                    "Do not invent callers, dependencies, execution paths, "
                    "or project relationships that are not present in the data.\n\n"

                    "Explain what the verified relationships mean from an "
                    "engineering perspective.\n\n"

                    "Discuss likely impact, risk, and what areas should be "
                    "tested or reviewed.\n\n"

                    "Clearly distinguish verified facts from reasonable "
                    "engineering recommendations.\n\n"

                    "Speak directly to the developer using 'you' and 'your'.\n"

                    "Do not refer to the developer as 'the user', 'he', "
                    "'him', or 'Chandler'.\n\n"

                    "Keep the response concise but useful."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original question:\n"
                    f"{command}\n\n"

                    f"Verified project impact data:\n"
                    f"{json.dumps(impact_data, indent=2)}"
                ),
            },
        ],
    )

    return response["message"]["content"]

def stream_ai_response(
    prompt,
    on_chunk=None,
):
    """
    Stream a conversational AI response using the same
    memory, conversation-topic, code, history, and system
    prompt logic used by ask_ai().
    """

    add_message(
        "user",
        prompt,
    )

    update_status("thinking")

    memory_context = get_memory_context()

    topic = get_topic()

    capability_context = get_capability_context()

    conversation_context = ""

    if topic:

        if topic["type"] == "file":

            conversation_context = (
                "\n\nCurrent conversation topic:\n"
                f"You are discussing the file "
                f"{topic['filename']}.\n"
                "The user may ask follow-up questions "
                "about this file without naming it again."
            )

    code_context = ""

    if topic:

        if topic["type"] == "file":

            file_info = get_file_content(
                topic["filename"]
            )

            if file_info:

                code_context = (
                    "\n\nCurrent file contents:\n\n"
                    f"{file_info['content']}"
                )

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS, a personal AI assistant "
                "created for your user."

                "\n\nYou are speaking directly to the user."

                "\nAlways address the user as 'you' and 'your'."

                "\nDo not refer to the user in the third person."

                "\nDo not call the user 'Chandler'."

                "\nDo not use phrases like 'he', 'him', "
                "'the user', or 'Chandler' when talking "
                "about the person you are speaking to."

                "\n\nWhen discussing stored memories, "
                "phrase them naturally."

                "\nExample: say 'Your project deadline is Friday.'"

                "\nExample: say 'You told me your project "
                "deadline is Friday.'"

                "\nDo not say \"User's name's project "
                "deadline is Friday.\""

                "\n\nThe following memories are facts "
                "about the person you are speaking to:\n\n"

                "\n\nCAPABILITY RULES:\n"
                f"{capability_context}\n"
                "\nNever invent capabilities, actions, access, "
                "information, or results.\n"
                "Never imply that you have information simply "
                "because the user asked about it.\n"
                "If a capability is unavailable, do not infer, "
                "guess, or imply the current state of that system.\n"
                "Do not say that something is empty, unavailable, "
                "completed, scheduled, sent, checked, or found unless "
                "you actually have the data or executed the capability "
                "that establishes that fact.\n"
                "Never claim that you checked a calendar, email, "
                "messages, browser, smart-home device, or other "
                "external system unless a real capability for that "
                "system is available and was actually executed.\n"

                f"{memory_context}"

                f"{conversation_context}"

                f"{code_context}"
            ),
        }
    ]

    messages.extend(
        get_history()
    )

    response = chat(
        model="llama3.1:8b",
        messages=messages,
        stream=True,
    )

    full_response = ""

    for chunk in response:

        try:
            content = chunk["message"]["content"]

        except (TypeError, KeyError):

            content = chunk.message.content

        if not content:
            continue

        full_response += content

        if on_chunk:
            on_chunk(content)

        yield content

    if full_response:
        add_message(
            "assistant",
            full_response,
        )

    update_status("listening")