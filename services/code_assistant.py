from ollama import chat


def answer_question(question, file_info):

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer.\n\n"

                    "The user is asking a question about the supplied source code.\n"

                    "Answer the specific question directly.\n"

                    "Do not summarize the entire file unless asked.\n"

                    "Reference specific functions, variables, and logic when appropriate."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Source Code:\n\n{file_info['content']}"
                ),
            },
        ],
    )

    return response["message"]["content"]