import pytest

import services.ai_service as ai_service

from models.information import (
    InformationSource,
)

from services.conversation_manager import (
    set_pending_request,
    clear_pending_request,
)

from services.grounding_service import (
    create_information_item,
)

from models.tool_request import ToolRequest


class FakeChunk:

    def __init__(self, text):
        self.data = {
            "message": {
                "content": text
            }
        }

    def __getitem__(self, key):
        return self.data[key]


def test_ask_ai_non_streaming(monkeypatch):

    captured = {}

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return {
            "message": {
                "content": "Hello from JARVIS."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [
            create_information_item(
                "Your project deadline is Friday.",
                InformationSource.REMEMBERED,
            )
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "Hello"
    )

    assert result == (
        "Hello from JARVIS."
    )

    assert captured["chat"]["stream"] is False

    assert (
        "[remembered] "
        "Your project deadline is Friday."
        in captured["chat"]["messages"][0]["content"]
    )

    assert saved_messages == [
        {
            "role": "user",
            "message": "Hello",
            "source": "user",
        },
        {
            "role": "assistant",
            "message": "Hello from JARVIS.",
            "source": "ollama",
        },
    ]

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": "Hello",
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "Hello from JARVIS.",
                "source": "ollama",
            },
        ]
    )


def test_ask_ai_streaming(monkeypatch):

    captured = {}

    streamed_chunks = []

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return iter(
            [
                FakeChunk("Hello "),
                FakeChunk("from "),
                FakeChunk("JARVIS."),
            ]
        )

    def fake_on_chunk(text):

        streamed_chunks.append(
            text
        )

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [
            create_information_item(
                "Your project deadline is Friday.",
                InformationSource.REMEMBERED,
            )
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "Hello",
        stream=True,
        on_chunk=fake_on_chunk,
    )

    assert result == (
        "Hello from JARVIS."
    )

    assert captured["chat"]["stream"] is True

    assert (
        "[remembered] "
        "Your project deadline is Friday."
        in captured["chat"]["messages"][0]["content"]
    )

    assert streamed_chunks == [
        "Hello ",
        "from ",
        "JARVIS.",
    ]

    assert saved_messages == [
        {
            "role": "user",
            "message": "Hello",
            "source": "user",
        },
        {
            "role": "assistant",
            "message": "Hello from JARVIS.",
            "source": "ollama",
        },
    ]

    assert (
        saved_messages
        == [
            {
                "role": "user",
                "message": "Hello",
                "source": "user",
            },
            {
                "role": "assistant",
                "message": "Hello from JARVIS.",
                "source": "ollama",
            },
        ]
    )

def test_ask_ai_receives_agent_result_context(
    monkeypatch,
):

    captured = {}

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return {
            "message": {
                "content": "I found the project information."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [
            {
                "role": "assistant",
                "content": (
                    "External agent result:\n"
                    "[agent_result] "
                    "The project contains 12 Python files."
                ),
            },
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "What did you find about the project?"
    )

    assert result == (
        "I found the project information."
    )

    messages = captured["chat"]["messages"]

    assert any(
        message["content"]
        == (
            "External agent result:\n"
            "[agent_result] "
            "The project contains 12 Python files."
        )
        for message in messages
    )

    assert saved_messages == [
        {
            "role": "user",
            "message": (
                "What did you find about the project?"
            ),
            "source": "user",
        },
        {
            "role": "assistant",
            "message": (
                "I found the project information."
            ),
            "source": "ollama",
        },
    ]

def test_ask_ai_receives_observed_tool_result_context(
    monkeypatch,
):

    captured = {}

    saved_messages = []

    def fake_add_message(
        role,
        message,
        source=None,
    ):
        saved_messages.append(
            {
                "role": role,
                "message": message,
                "source": source,
            }
        )

    def fake_chat(
        **kwargs,
    ):

        captured["chat"] = kwargs

        return {
            "message": {
                "content": "Your current Git branch is main."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "add_message",
        fake_add_message,
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [
            {
                "role": "assistant",
                "content": (
                    "Observed tool result:\n"
                    "[observed] branch: main"
                ),
            },
        ],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    result = ai_service.ask_ai(
        "What branch am I currently on?"
    )

    assert result == (
        "Your current Git branch is main."
    )

    messages = captured["chat"]["messages"]

    assert any(
        message["content"]
        == (
            "Observed tool result:\n"
            "[observed] branch: main"
        )
        for message in messages
    )

    assert saved_messages == [
        {
            "role": "user",
            "message": (
                "What branch am I currently on?"
            ),
            "source": "user",
        },
        {
            "role": "assistant",
            "message": (
                "Your current Git branch is main."
            ),
            "source": "ollama",
        },
    ]

def test_ask_ai_includes_grounding_rules_in_system_prompt(
    monkeypatch,
):
    captured = {}

    def fake_chat(**kwargs):
        captured["chat"] = kwargs

        return {
            "message": {
                "content": "I can only report what was actually observed."
            }
        }

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    ai_service.ask_ai(
        "What do you know about my current state?"
    )

    system_message = captured["chat"]["messages"][0]

    assert system_message["role"] == "system"

    prompt = system_message["content"]

    assert "Never invent capabilities" in prompt
    assert "[observed]" in prompt
    assert "[remembered]" in prompt
    assert "[agent_result]" in prompt
    assert "not automatically verified" in prompt
    assert "inferred information" in prompt

def test_ask_ai_includes_pending_clarification_context(
    monkeypatch,
):
    captured = {}

    def fake_chat(**kwargs):
        captured["chat"] = kwargs

        return {
            "message": {
                "content": "Which file would you like me to explain?"
            }
        }

    set_pending_request(
        {
            "request": ToolRequest(
                tool="explain_file",
                arguments={},
            ),
            "missing": "filename",
            "candidates": None,
            "prompt": (
                "Sure. Which file would you like me to explain?"
            ),
        }
    )

    monkeypatch.setattr(
        ai_service,
        "get_memory_information",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "get_topic",
        lambda: None,
    )

    monkeypatch.setattr(
        ai_service,
        "get_capability_context",
        lambda: "No capabilities available.",
    )

    monkeypatch.setattr(
        ai_service,
        "get_source_aware_history",
        lambda: [],
    )

    monkeypatch.setattr(
        ai_service,
        "update_status",
        lambda status: None,
    )

    monkeypatch.setattr(
        ai_service,
        "chat",
        fake_chat,
    )

    try:
        ai_service.ask_ai(
            "Which file?"
        )

        system_message = (
            captured["chat"]["messages"][0]
        )

        prompt = system_message["content"]

        assert "Pending clarification:" in prompt
        assert (
            "JARVIS is waiting for the user "
            "to provide filename."
            in prompt
        )
        assert (
            "Sure. Which file would you like me to explain?"
            in prompt
        )

    finally:
        clear_pending_request()


@pytest.mark.parametrize("context_kind", ["full", "empty", "missing_file", "no_prompt"])
def test_conversation_paths_receive_identical_system_rules_and_context(
    monkeypatch, context_kind,
):
    captured = {}
    saved = []
    statuses = []
    topic = None if context_kind == "empty" else {
        "type": "file", "filename": "router.py", "depth": 2,
    }
    pending = None if context_kind == "empty" else {
        "request": ToolRequest("explain_file"),
        "missing": "filename",
        "prompt": "Which file should I explain?" if context_kind != "no_prompt" else "",
    }
    history = [
        {"role": "assistant", "content": "[observed] branch: main"},
        {"role": "assistant", "content": "[agent_result] branch: development"},
        {"role": "user", "content": "Explain that."},
    ]
    monkeypatch.setattr(ai_service, "get_topic", lambda: topic)
    monkeypatch.setattr(ai_service, "get_pending_request", lambda: pending)
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: [] if context_kind == "empty" else [
        create_information_item("Your deadline is Friday.", InformationSource.REMEMBERED),
    ])
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "Calendar [unavailable]; current_time [available]")
    monkeypatch.setattr(ai_service, "get_source_aware_history", lambda: list(history))
    monkeypatch.setattr(ai_service, "update_status", statuses.append)
    monkeypatch.setattr(ai_service, "add_message", lambda role, text, source: saved.append((role, text, source)))

    def get_file(filename):
        assert filename == "router.py"
        return None if context_kind == "missing_file" else {"content": "def process(command): pass"}

    def chat(**kwargs):
        captured["ollama"] = kwargs
        if kwargs["stream"]:
            return iter([FakeChunk("Hello"), FakeChunk(""), FakeChunk(" there.")])
        return {"message": {"content": "Hello there."}}

    class Hermes:
        def stream_prompt(self, session_id, prompt, timeout):
            assert session_id == "test-session"
            assert timeout == 300
            captured["hermes"] = prompt
            return iter(["Hello", "", " there."])

    monkeypatch.setattr(ai_service, "get_file_content", get_file)
    monkeypatch.setattr(ai_service, "chat", chat)
    monkeypatch.setattr(ai_service, "get_hermes_session", lambda: (Hermes(), "test-session"))

    assert ai_service.ask_ai("Explain that.") == "Hello there."
    messages = captured["ollama"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1:] == history
    assert captured["ollama"]["stream"] is False

    chunks = []
    assert ai_service.ask_ai("Explain that.", stream=True, on_chunk=chunks.append) == "Hello there."
    assert captured["ollama"]["messages"] == messages
    assert captured["ollama"]["stream"] is True
    assert chunks == ["Hello", " there."]

    chunks = []
    assert list(ai_service.stream_ai_response("Explain that.", on_chunk=chunks.append)) == ["Hello", " there."]
    assert chunks == ["Hello", " there."]
    # Compare the actual provider payloads, including all rules and source-aware history.
    assert captured["hermes"] == "\n\n".join(
        f"--- {message['role'].upper() if message['role'] != 'system' else 'SYSTEM INSTRUCTIONS'} ---\n{message['content']}"
        for message in messages
    )

    system = messages[0]["content"]
    for rule in [
        "You are JARVIS, a personal AI assistant",
        "Always address the user as 'you' and 'your'.",
        "When answering normal conversational questions, answer directly and naturally.",
        "Do not use tools, code execution, terminal commands, browser tools, or other external actions for simple questions that you can answer directly.",
        "Only use a tool when the user's request genuinely requires an external action or information that cannot be answered from the conversation context.",
        "Never invent capabilities, actions, access, information, or results.",
        "Never imply that you have information simply because the user asked about it.",
        "If a capability is unavailable, do not infer, guess, or imply the current state of that system.",
        "Do not say that something is empty, unavailable, completed, scheduled, sent, checked, or found unless you actually have the data or executed the capability that establishes that fact.",
        "Never claim that you checked a calendar, email, messages, browser, smart-home device, or other external system unless a real capability for that system is available and was actually executed.",
        "Treat [observed] information as information returned by a real tool or source.",
        "Treat [remembered] information as information retrieved from persistent memory.",
        "Treat [agent_result] information as a report produced by an external agent. It is not automatically verified.",
        "Treat inferred information as reasoning or interpretation, not as a directly observed fact.",
        "Never silently upgrade inferred or agent-reported information into observed information.",
        "When provenance matters, preserve the distinction in your response.",
        "If information conflicts, acknowledge the conflict rather than silently choosing a source.",
        "Treat it as remembered information, not as something you directly observed:",
        "Calendar [unavailable]; current_time [available]",
    ]:
        assert rule in system

    assert ("You are discussing the file router.py." in system) == (topic is not None)
    assert ("[remembered] Your deadline is Friday." in system) == (context_kind != "empty")
    assert ("Current file contents:" in system) == (context_kind not in {"empty", "missing_file"})
    if topic and context_kind != "missing_file":
        assert "def process(command): pass" in system
    assert ("Pending clarification:" in system) == (context_kind not in {"empty", "no_prompt"})
    if pending and pending["prompt"]:
        assert "JARVIS is waiting for the user to provide filename." in system
        assert pending["prompt"] in system
    assert statuses == ["thinking", "thinking", "thinking", "listening"]
    assert saved == [
        ("user", "Explain that.", "user"),
        ("assistant", "Hello there.", "ollama"),
        ("user", "Explain that.", "user"),
        ("assistant", "Hello there.", "ollama"),
        ("user", "Explain that.", "user"),
        ("assistant", "Hello there.", "hermes"),
    ]
