from ollama import chat

def ask_ai(prompt):
    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are JARVIS, a concise AI assistant. "
                    "Keep answers under 3 sentences unless asked for detail."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response["message"]["content"]