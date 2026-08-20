from services.prompt_builder import (
    build_code_question_prompt,
)


def test_build_code_question_prompt_includes_project_context():

    file_info = {
        "filename": "router.py",
        "content": "def process(command): pass",
    }

    project_context = (
        "===== PROJECT ANALYSIS =====\n"
        "process() calls execute_tool()."
    )

    prompt = build_code_question_prompt(
        "What does process call?",
        file_info,
        project_context=project_context,
    )

    assert "router.py" in prompt
    assert "What does process call?" in prompt
    assert "def process(command): pass" in prompt
    assert "PROJECT ANALYSIS" in prompt
    assert "process() calls execute_tool()" in prompt

def test_build_code_question_prompt_includes_conversation_context():

    file_info = {
        "filename": "router.py",
        "content": "def process(command): pass",
    }

    conversation_context = {
        "topic": {
            "filename": "router.py",
        },
        "recent_turns": [
            {
                "role": "user",
                "content": "What does process do?",
            },
            {
                "role": "assistant",
                "content": "It routes commands.",
            },
        ],
    }

    prompt = build_code_question_prompt(
        "What does it call?",
        file_info,
        conversation_context=conversation_context,
    )

    assert "Current Conversation Topic:" in prompt
    assert "What does process do?" in prompt
    assert "It routes commands." in prompt

def test_build_code_question_prompt_works_without_optional_context():

    file_info = {
        "filename": "router.py",
        "content": "def process(command): pass",
    }

    prompt = build_code_question_prompt(
        "What does process do?",
        file_info,
    )

    assert "router.py" in prompt
    assert "What does process do?" in prompt
    assert "def process(command): pass" in prompt