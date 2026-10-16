import pytest

from services.command_parser import parse_command
from services.historical_recall import classify_historical_recall


@pytest.mark.parametrize("target,expected", [
    ("the file actions.py", "actions.py"),
    ("file actions.py", "actions.py"),
    ("actions.py", "actions.py"),
    ("the actions.py", "actions.py"),
    ("my file notes.py", "my file notes.py"),
    ("file my file notes.py", "my file notes.py"),
    ("the file weather the file.py", "weather the file.py"),
    ("file file actions.py", "file actions.py"),
    ("the file the file notes.py", "the file notes.py"),
    ('"file actions.py"', "file actions.py"),
    ('file "file actions.py"', "file actions.py"),
    ('"the notes.py"', "the notes.py"),
    ("file.py", "file.py"),
    (".env", ".env"),
    ("services/my file.py", "services/my file.py"),
])
def test_summary_filename_preserves_literal_target(target, expected):
    parsed = parse_command("summarize " + target)
    assert parsed.tool == "summarize_file"
    assert parsed.arguments == {"filename": expected}


@pytest.mark.parametrize("utterance", [
    "summarize our", "summarize our last", "summarize our la-",
    "please summarize our last con-", "summarize our previous",
    "summarize our last conversation", "summarize our previous discussion",
])
def test_conversation_summary_is_never_a_file(utterance):
    assert parse_command(utterance) is None


def test_historical_and_conceptual_routing_are_unchanged():
    assert classify_historical_recall("Summarize our last conversation").session_scope == "previous"
    assert classify_historical_recall("Did we discuss inheritance?").topic == "inheritance"
    assert classify_historical_recall("What is inheritance?") is None
