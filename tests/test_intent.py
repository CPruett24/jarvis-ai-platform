from services.code_intent import (
    is_code_question,
    is_contextual_code_question,
)
from services.intent_resolver import resolve_intent


def test_why_question_is_code_question():

    assert is_code_question(
        "why is aliases here"
    )


def test_how_question_is_code_question():

    assert is_code_question(
        "how does this function work"
    )


def test_normal_command_is_not_code_question():

    assert not is_code_question(
        "open github"
    )


def test_general_statement_is_not_code_question():

    assert not is_code_question(
        "hello jarvis"
    )

def test_contextual_design_question_is_detected():

    assert is_contextual_code_question(
        "what would you change first"
    )


def test_contextual_improvement_question_is_detected():

    assert is_contextual_code_question(
        "how could this be improved"
    )


def test_contextual_recommendation_question_is_detected():

    assert is_contextual_code_question(
        "what would you recommend"
    )


def test_normal_command_is_not_contextual_code_question():

    assert not is_contextual_code_question(
        "open github"
    )

def test_general_command_resolves_to_tool():

    intent = resolve_intent(
        "open github"
    )

    assert intent.type == "tool"
    assert intent.tool_request is not None


def test_general_conversation_resolves_to_conversation():

    intent = resolve_intent(
        "hello jarvis"
    )

    assert intent.type == "conversation"


def test_code_question_resolves_to_code_question():

    from services.conversation_manager import (
        set_topic,
        clear_topic,
        clear_context,
    )

    clear_context()

    set_topic(
        {
            "type": "file",
            "filename": "router.py",
            "depth": 1,
        }
    )

    intent = resolve_intent(
        "why is aliases here"
    )

    assert intent.type == "code_question"

    clear_topic()
    clear_context()

def test_impact_analysis_resolves_to_impact_analysis():

    intent = resolve_intent(
        "what would be affected if I change execute_tool"
    )

    assert intent.type == "impact_analysis"
    assert intent.confidence == 0.95


def test_impact_analysis_detects_dependencies():

    intent = resolve_intent(
        "what depends on execute_tool"
    )

    assert intent.type == "impact_analysis"


def test_impact_analysis_detects_breakage_question():

    intent = resolve_intent(
        "what would break if I change router.py"
    )

    assert intent.type == "impact_analysis"

def test_impact_analysis_detects_natural_change_question():

    result = resolve_intent(
        "would break if i modify router.py"
    )

    assert result.type == "impact_analysis"


def test_impact_analysis_detects_edit_question():

    result = resolve_intent(
        "what could be affected if i edit router.py"
    )

    assert result.type == "impact_analysis"