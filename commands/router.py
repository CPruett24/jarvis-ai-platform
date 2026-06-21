from services.ai_service import ask_ai, detect_intent
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
    "what's the time": "what time is it",
    "tell me the time": "what time is it",
    "what time is it right now": "what time is it",
    "can you tell me the time": "what time is it",
}

COMMANDS = {
    "hello": hello,
    "open vscode": open_vscode,
    "what time is it": current_time,
    "open github": open_github,
    "open chatgpt": open_chatgpt,
    "what do you remember": recall_memories,
}

INTENT_COMMANDS = {
    "hello": hello,
    "open_vscode": open_vscode,
    "current_time": current_time,
    "open_github": open_github,
    "open_chatgpt": open_chatgpt,
    "recall_memories": recall_memories,
}


def process(command):
    command = command.lower()

    command = command.strip(".,!?")

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
        return

    intent = detect_intent(command)

    print(f"Detected intent: {intent}")

    if intent != "none":

        intents = [
            i.strip()
            for i in intent.split(",")
        ]

        for single_intent in intents:

            intent_action = INTENT_COMMANDS.get(
                single_intent
            )

            if intent_action:
                intent_action()

        return

    response = ask_ai(command)

    speak(response)
