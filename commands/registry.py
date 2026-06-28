from commands.actions import (
    hello,
    open_vscode,
    current_time,
    open_github,
    open_chatgpt,
    recall_memories,
    open_coding_workspace,
    open_aws_workspace,
    open_school_workspace,
)

COMMAND_REGISTRY = {
    "hello": {
        "function": hello,
        "description": "Greets the user."
    },

    "open_vscode": {
        "function": open_vscode,
        "description": "Opens Visual Studio Code."
    },

    "current_time": {
        "function": current_time,
        "description": "Tells the current time."
    },

    "open_github": {
        "function": open_github,
        "description": "Opens GitHub."
    },

    "open_chatgpt": {
        "function": open_chatgpt,
        "description": "Opens ChatGPT."
    },

    "recall_memories": {
        "function": recall_memories,
        "description": "Reads saved memories."
    },

    "open_coding_workspace": {
        "function": open_coding_workspace,
        "description": "Launches the coding workspace."
    },

    "open_aws_workspace": {
        "function": open_aws_workspace,
        "description": "Launches the AWS workspace."
    },

    "open_school_workspace": {
        "function": open_school_workspace,
        "description": "Launches the school workspace."
    },

}