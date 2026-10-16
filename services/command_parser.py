import re

from models.tool_request import ToolRequest

def normalize_filename(text):

    return (
        text.strip()
        .strip(".")
        .replace("the ", "")
    )


def normalize_summary_filename(text):
    """Remove one spoken target introducer, never words inside the filename.

    Quotes disambiguate literal names beginning with 'file ' or 'the '.
    """
    text = text.strip()
    if not text.startswith(('"', "'")):
        match = re.fullmatch(r"(?:the\s+)?file\s+(.+)", text, re.I)
        text = match[1] if match else re.sub(r"^the\s+", "", text, count=1, flags=re.I)
    if len(text) >= 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1]
    return text

def parse_command(command):

    command = command.lower().strip()
    from services.code_intent import is_conversation_summary_phrase
    if is_conversation_summary_phrase(command):
        return None

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
                "filename": normalize_summary_filename(
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

def parse_workspace_command(command):
    """
    Detect natural-language requests to open a configured workspace.

    Returns a ToolRequest when the request clearly identifies
    a supported workspace, otherwise returns None.
    """

    command = command.lower().strip()

    if not re.fullmatch(
        r"(?:(?:can you |could you )?(?:also )?|please )"
        r"(?:open|launch) (?:my |the )?(?:coding|aws|school) workspace",
        command.rstrip(".!?"),
    ):
        return None

    if "coding" in command:
        return ToolRequest(
            tool="open_coding_workspace"
        )

    if "aws" in command:
        return ToolRequest(
            tool="open_aws_workspace"
        )

    if "school" in command:
        return ToolRequest(
            tool="open_school_workspace"
        )

    return None
