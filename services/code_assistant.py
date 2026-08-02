from ollama import chat


def answer_question(question, file_info):

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are JARVIS, an experienced senior software engineer.\n\n"

                    "You are helping the user understand their own codebase.\n"

                    "The supplied source code is the current discussion topic.\n"

                    "Answer ONLY the user's question.\n"

                    "Do not summarize the file unless the user explicitly asks for a summary.\n"

                    "Reference specific functions, variables, imports, and control flow whenever appropriate.\n"

                    "If you suggest improvements, explain why they would improve the design.\n"

                    "Assume the user is the author of this project."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current File: {file_info['filename']}\n\n"

                    f"Question:\n{question}\n\n"

                    f"Source Code:\n\n{file_info['content']}"
                ),
            },
        ],
    )

    return response["message"]["content"]