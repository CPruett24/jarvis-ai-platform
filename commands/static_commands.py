from commands.actions import (
    hello,
    open_vscode,
    current_time,
    open_github,
    open_chatgpt,
    recall_memories,
)

COMMANDS = {
    "hello": "hello",
    "open vscode": "open_vscode",
    "what time is it": "current_time",
    "open github": "open_github",
    "open chatgpt": "open_chatgpt",
    "what do you remember": "recall_memories",
    "where am i": "current_directory",
    "list files": "list_files",
    "list the files": "list_files",
    "tell me about this computer": "system_info",
    "what project am i in": "current_project",
    "what branch am i on": "git_branch",
    "git status": "git_status",
    "what git remotes do i have": "git_remote",
    "what version of python am i running": "python_version",
    "show me the project structure": "project_tree",
    "project structure": "project_tree",
}