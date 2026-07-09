import re

from models.tool_request import ToolRequest

def normalize_filename(text):

    return (
        text.strip()
        .strip(".")
        .replace("the ", "")
    )

def parse_command(command):

    command = command.lower().strip()

    # Explain
    match = re.match(
        r"^(?:can you |could you |please )?(?:explain|explaining)\s+(.+)$",
        command,
    )

    if match:
        return ToolRequest(
            tool="explain_file",
            arguments={
                "filename": normalize_filename(
                match.group(1)
                )
            }
        )

    # Summarize
    match = re.match(
        r"^(?:can you |could you |please )?(?:summarize|summarise|summarizing)\s+(.+)$",
        command,
    )

    if match:
        return ToolRequest(
            tool="summarize_file",
            arguments={
                "filename": normalize_filename(
                match.group(1)
                )
            }
        )

    # Find
    match = re.match(
        r"^(?:find|locate)\s+(.+)$",
        command,
    )

    if match:
        return ToolRequest(
            tool="find_file",
            arguments={
                "filename": normalize_filename(
                match.group(1)
                )
            }
        )

    # Search
    match = re.match(
        r"^(?:search for|look for)\s+(.+)$",
        command,
    )

    if match:
        return ToolRequest(
            tool="search_project",
            arguments={
                "keyword": match.group(1).strip()
            }
        )

    return None