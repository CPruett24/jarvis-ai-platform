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
    current_directory,
    list_files,
    system_info,
    current_project,
    git_branch,
    git_status,
    git_remote,
    python_version,
    project_tree,
    find_file,
    summarize_file_action,
    search_project_action,
    explain_file_action,
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

    "current_directory": {
    "function": current_directory,
    "description": "Returns the current working directory."
    },

    "list_files": {
        "function": list_files,
        "description": "Lists the files in the current directory."
    },

    "system_info": {
        "function": system_info,
        "description": "Returns information about the current computer."
    },

    "current_project": {
    "function": current_project,
    "description": "Returns the current project name."
    },

    "git_branch": {
        "function": git_branch,
        "description": "Returns the current Git branch."
    },

    "git_status": {
        "function": git_status,
        "description": "Returns the Git repository status."
    },

    "git_remote": {
        "function": git_remote,
        "description": "Lists configured Git remotes."
    },

    "python_version": {
        "function": python_version,
        "description": "Returns the installed Python version."
    },

    "project_tree": {
    "function": project_tree,
    "description": "Shows the top-level project structure."
    },

    "find_file": {
        "function": find_file,
        "description": "Finds a file within the project."
    },
    "summarize_file": {
    "function": summarize_file_action,
    "description": "Summarizes a project file."
    },

    "search_project": {
        "function": search_project_action,
        "description": "Searches the project for text."
    },

    "explain_file": {
        "function": explain_file_action,
        "description": "Explains the purpose of a source code file."
    },

}