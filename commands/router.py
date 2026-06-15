from commands.actions import (
    hello,
    open_vscode,
    current_time,
    open_github,
    open_chatgpt,
    unknown,
)

COMMANDS = {
    "hello": hello,
    "open vscode": open_vscode,
    "what time is it": current_time,
    "open github": open_github,
    "open chatgpt": open_chatgpt,
}


def process(command):
    command = command.lower()

    action = COMMANDS.get(command, unknown)

    action()