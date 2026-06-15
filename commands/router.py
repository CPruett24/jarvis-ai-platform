from commands.actions import (
    hello,
    open_vscode,
    current_time,
    open_github,
    open_chatgpt,
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
}


def process(command):
    command = command.lower()

    # Translate aliases into actual commands
    command = ALIASES.get(command, command)

    action = COMMANDS.get(command, unknown)

    action()