def build_code_question_prompt(
    question,
    file_info,
    conversation_context=None,
    project_context=None,
):

    prompt = (
        f"Current File: {file_info['filename']}\n\n"
        f"Question:\n{question}\n\n"
        f"Source Code:\n\n{file_info['content']}"
    )

    if project_context:

        prompt += (
            "\n\nProject Context:\n"
            f"{project_context}"
        )

    if conversation_context:

        topic = conversation_context.get("topic")

        recent_turns = conversation_context.get(
            "recent_turns",
            []
        )

        if topic:

            prompt += (
                "\n\nCurrent Conversation Topic:\n"
                f"{topic}"
            )

        if recent_turns:

            prompt += (
                "\n\nRecent Conversation:\n"
            )

            for turn in recent_turns:

                prompt += (
                    f"{turn['role'].capitalize()}: "
                    f"{turn['content']}\n"
                )

    return prompt