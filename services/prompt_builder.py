def build_code_question_prompt(
    question,
    file_info,
):
    return (
        f"Current File: {file_info['filename']}\n\n"

        f"Question:\n{question}\n\n"

        f"Source Code:\n\n{file_info['content']}"
    )