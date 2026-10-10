import pytest

from services import ai_service
from services.grounding_service import create_memory_information, format_information_context
from services.memory_selection import (
    select_memory_information, MAX_MEMORY_ITEMS, MAX_MEMORY_CONTEXT_CHARS,
)


@pytest.fixture
def memories():
    return [create_memory_information(text) for text in (
        "You worked on a Python weather application project.",
        "Your favorite food is sushi.",
        "You prefer concise explanations.",
    )]


@pytest.mark.parametrize("question", ["What is OOP?", "What is Python?", "What is sushi?"])
def test_generic_questions_exclude_even_overlapping_memories(question, memories):
    assert select_memory_information(question, memories) == []


@pytest.mark.parametrize("question", [
    "What programming projects have I worked on?",
    "Explain OOP using one of my projects as an example.",
    "What do you remember about my projects?",
])
def test_personal_projects_preserve_content_and_provenance(question, memories):
    result = select_memory_information(question, memories)
    assert result == [memories[0]]
    assert result[0] is memories[0]
    assert format_information_context(result).startswith("[remembered] You worked")


def test_personal_followup_uses_only_user_antecedent(memories):
    question = "Can you explain that more simply?"
    history = [{"role": "user", "content": "Explain OOP using my projects."},
               {"role": "assistant", "content": "Your favorite food is sushi."},
               {"role": "user", "content": question}]
    assert select_memory_information(question, memories, history) == [memories[0]]
    assert select_memory_information(question, memories, history[1:]) == []


def test_bounds_and_order_are_deterministic():
    items = [create_memory_information(f"Project {i:03}: " + "x" * 400) for i in range(100)]
    items.append(create_memory_information("Project " + "x" * 3000))
    result = select_memory_information("Tell me about my projects", items)
    assert result == select_memory_information("Tell me about my projects", list(reversed(items)))
    assert 0 < len(result) <= MAX_MEMORY_ITEMS
    assert len(format_information_context(result)) <= MAX_MEMORY_CONTEXT_CHARS
    short = [create_memory_information(f"Project {i}") for i in range(20)]
    assert len(select_memory_information("my projects", short)) == MAX_MEMORY_ITEMS


def test_all_ollama_paths_select_identical_personal_memory(monkeypatch, memories):
    captured = []
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: memories)
    monkeypatch.setattr(ai_service, "get_source_aware_history", lambda: [])
    monkeypatch.setattr(ai_service, "get_topic", lambda: None)
    monkeypatch.setattr(ai_service, "get_pending_request", lambda: None)
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "")
    monkeypatch.setattr(ai_service, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(ai_service, "update_status", lambda *a: None)

    def chat(**kwargs):
        captured.append(kwargs["messages"])
        response = {"message": {"content": "answer"}}
        return iter([response]) if kwargs["stream"] else response

    monkeypatch.setattr(ai_service, "chat", chat)
    question = "What programming projects have I worked on?"
    ai_service.ask_ai(question)
    ai_service.ask_ai(question, stream=True)
    list(ai_service.stream_ai_response(question))
    assert captured[0] == captured[1] == captured[2]
    assert "[remembered] " + memories[0].content in captured[0][0]["content"]
    assert memories[1].content not in captured[0][0]["content"]


@pytest.mark.parametrize("question", [
    "What is REST?", "What is object-oriented programming?",
    "What about inheritance?", "Can you explain that more simply?",
    "How does that compare to functional programming?",
])
def test_history_stays_context_without_becoming_evidence(monkeypatch, memories, question):
    history = [{"role": "user", "content": "What is OOP?"},
               {"role": "assistant", "content": "OOP uses objects. You've built several web applications."}]
    monkeypatch.setattr(ai_service, "get_source_aware_history", lambda: history)
    monkeypatch.setattr(ai_service, "get_memory_information", lambda: memories)
    monkeypatch.setattr(ai_service, "get_topic", lambda: None)
    monkeypatch.setattr(ai_service, "get_pending_request", lambda: None)
    monkeypatch.setattr(ai_service, "get_capability_context", lambda: "")
    messages = ai_service._build_conversation_messages(question)
    assert messages[1:] == history
    system = messages[0]["content"]
    assert "NOT evidence" in system
    assert "independently supported" in system
    assert "unsolicited repetition commentary" in system
    assert "resolve a genuine follow-up or referent" in system
    assert "You've built several web applications." not in system
    assert "[remembered] You worked" not in system
    assert not any(tag in history[1]["content"] for tag in ("[remembered]", "[observed]", "[user_provided]"))
