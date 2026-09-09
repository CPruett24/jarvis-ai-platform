from models.tool_request import ToolRequest
from services.command_parser import parse_workspace_command


def test_parse_coding_workspace_request():
    request = parse_workspace_command(
        "can you open my coding workspace"
    )

    assert isinstance(request, ToolRequest)
    assert request.tool == "open_coding_workspace"


def test_parse_school_workspace_request():
    request = parse_workspace_command(
        "can you also open my school workspace"
    )

    assert isinstance(request, ToolRequest)
    assert request.tool == "open_school_workspace"


def test_parse_aws_workspace_request():
    request = parse_workspace_command(
        "please open my AWS workspace"
    )

    assert isinstance(request, ToolRequest)
    assert request.tool == "open_aws_workspace"


def test_workspace_parser_ignores_unrelated_text():
    request = parse_workspace_command(
        "tell me about workspace architecture"
    )

    assert request is None