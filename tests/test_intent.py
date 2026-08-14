from services.code_intent import (
    is_code_question,
    is_contextual_code_question,
)


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