from ollama import chat
from services.prompt_builder import build_code_question_prompt


def answer_question(
    question,
    file_info,
    conversation_context=None,
):

    prompt = build_code_question_prompt(
        question,
        file_info,
        conversation_context,
    )

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are JARVIS, an experienced senior software engineer.\n\n"

                    "You are helping the user understand their own codebase.\n\n"

                    "The supplied source code is the current discussion topic.\n\n"

                    "Use the recent conversation and current topic to "
                    "understand what the user is referring to.\n\n"

                    "If the user asks a follow-up question, answer it in "
                    "the context of the previous discussion.\n\n"

                    "Answer the user's specific question directly.\n\n"

                    "Do not summarize the entire file unless the user "
                    "explicitly asks for a summary.\n\n"

                    "Reference specific functions, variables, imports, "
                    "and control flow whenever appropriate.\n\n"

                    "If you suggest improvements, explain why they would "
                    "improve the design.\n\n"

                    "Do not assume architectural patterns that are not "
                    "visible in the supplied code.\n\n"

                    "If the supplied code does not provide enough "
                    "information to answer confidently, say so instead "
                    "of guessing.\n\n"

                    "Speak directly to the user."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response["message"]["content"]