from services.ai_service import chat, OLLAMA_MODEL

from services.project_context import (
    get_full_project_context,
)

from services.prompt_builder import (
    build_code_question_prompt,
)


SYSTEM_PROMPT = (
    "You are JARVIS, an experienced senior software engineer.\n\n"

    "You are helping the user understand and improve "
    "the supplied codebase.\n\n"

    "The supplied source code is the current discussion topic.\n\n"

    "The supplied project context contains both "
    "relevant project documentation and the actual "
    "current project state.\n\n"

    "Project documentation describes intended goals, "
    "architecture, principles, and roadmap.\n\n"

    "Current project state describes what actually "
    "exists in the codebase right now.\n\n"

    "Project analysis contains verified static-analysis "
    "relationships from the current codebase.\n\n"

    "Always distinguish between planned functionality "
    "and functionality that already exists.\n\n"

    "Use the project context to understand why the "
    "codebase is designed the way it is.\n\n"

    "Do not assume that documentation describes code "
    "that does not currently exist.\n\n"

    "The current source code is authoritative for what "
    "currently exists.\n\n"

    "Static-analysis facts are authoritative for indexed "
    "relationships such as callers, callees, and dependencies.\n\n"

    "Answer ONLY the user's question.\n\n"

    "Do not summarize the file unless the user explicitly "
    "asks for a summary.\n\n"

    "Reference specific functions, variables, imports, "
    "and control flow whenever appropriate.\n\n"

    "When suggesting changes, distinguish between:\n"
    "1. What exists today.\n"
    "2. What the project plans to build.\n"
    "3. What you recommend changing.\n\n"

    "When discussing architecture, align recommendations "
    "with the project's documented engineering principles "
    "and long-term direction.\n\n"

    "Do not recommend creating a file, service, feature, "
    "or capability that is already present in the current "
    "project state unless you are specifically recommending "
    "replacing or redesigning it.\n\n"

    "Do not assume the user authored this project or has particular experience "
    "unless supported by user-provided or verified information."
)


def answer_question(
    question,
    file_info,
    conversation_context=None,
):
    if file_info.get("evidence") is not None:
        from services.ai_service import generate_source_answer
        from services.source_answer import validate_answer, evidence_is_current
        result = file_info["evidence"]
        answer = validate_answer(generate_source_answer(question, result), result)
        if not answer or not evidence_is_current(result):
            return "I couldn't produce a current, source-referenced answer. Please retry."
        return "Interpretation of retrieved source:\n" + answer

    project_context = get_full_project_context(
        question
    )

    prompt = build_code_question_prompt(
        question,
        file_info,
        conversation_context=conversation_context,
        project_context=project_context,
    )

    response = chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response["message"]["content"]
