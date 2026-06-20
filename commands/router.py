from services.ai_service import ask_ai
from services.speaker import speak

from commands.actions import (
    hello,
    open_vscode,
    current_time,
    open_github,
    open_chatgpt,
    remember_command,
    recall_memories,
    search_memory_command,
    forget_memory_command,
    unknown,
)

ALIASES = {
    "open chat gpt": "open chatgpt",
    "open chat g p t": "open chatgpt",
    "what's the time": "what time is it",
    "tell me the time": "what time is it",
    "hi": "hello",
    "hey": "hello",
}

COMMANDS = {
    "hello": hello,
    "open vscode": open_vscode,
    "what time is it": current_time,
    "open github": open_github,
    "open chatgpt": open_chatgpt,
    "what do you remember": recall_memories,
}


def process(command):
    command = command.lower()

    command = ALIASES.get(command, command)

    # Dynamic memory commands
    if command.startswith("remember"):
        remember_command(command)

        return
    
    if command.startswith("what do you remember about"):
        search_memory_command(command)

        return
    
    if command.startswith("forget"):
        forget_memory_command(command)

        return

    action = COMMANDS.get(command)

    if action:
        action()
    else:
        response = ask_ai(command)

        speak(response)
