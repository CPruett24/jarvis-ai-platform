from services import code_assistant


def test_answer_question_uses_project_aware_prompt(monkeypatch):

    captured = {}

    def fake_context(question):
        return (
            "===== PROJECT ANALYSIS =====\n"
            "process() calls execute_tool()."
        )

    def fake_chat(model, messages):

        captured["model"] = model
        captured["messages"] = messages

        return {
            "message": {
                "content": "process calls execute_tool."
            }
        }

    monkeypatch.setattr(
        code_assistant,
        "get_full_project_context",
        fake_context,
    )

    monkeypatch.setattr(
        code_assistant,
        "chat",
        fake_chat,
    )

    file_info = {
        "filename": "router.py",
        "content": "def process(command): pass",
    }

    result = code_assistant.answer_question(
        "What does process call?",
        file_info,
    )

    assert result == (
        "process calls execute_tool."
    )

    assert captured["model"] == "llama3.1:8b"

    user_message = captured["messages"][1]["content"]

    assert "PROJECT ANALYSIS" in user_message
    assert "process() calls execute_tool()" in user_message