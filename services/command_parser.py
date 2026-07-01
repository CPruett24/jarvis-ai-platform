import re

from models.tool_request import ToolRequest


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
                "filename": match.group(1).strip()
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
                "filename": match.group(1).strip()
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
                "filename": match.group(1).strip()
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