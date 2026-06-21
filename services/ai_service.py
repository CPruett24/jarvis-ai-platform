from ollama import chat
from services.conversation_service import add_user_message, add_assistant_message, get_history
from services.memory_service import get_memory_context

def ask_ai(prompt):

    add_user_message(prompt)

    memory_context = get_memory_context()

    print("\nMEMORY CONTEXT:")
    print(memory_context)
    print()

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS, a personal AI assistant created for your user."

                "\n\nYou are speaking directly to the user."

                "\nAlways address the user as 'you' and 'your'."

                "\nDo not refer to the user in the third person."

                "\nDo not call the user 'Chandler'."

                "\nDo not use phrases like 'he', 'him', 'the user', or 'Chandler' when talking about the person you are speaking to."

                "\n\nWhen discussing stored memories, phrase them naturally."

                "\nExample: say 'Your AWS exam is August 15th.'"

                "\nExample: say 'You told me your AWS exam is August 15th.'"

                "\nDo not say \"Chandler's AWS exam is August 15th.\""

                "\n\nThe following memories are facts about the person you are speaking to:\n\n"

                f"{memory_context}"
            ),
        }
    ]

    messages.extend(get_history())

    response = chat(
        model="llama3.1:8b",
        messages=messages,
    )

    answer = response["message"]["content"]

    add_assistant_message(answer)

    return answer

def detect_intent(command):

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an intent classifier.\n\n"

                    "Your job is to determine whether the user is requesting one of the listed actions.\n\n"

                    "Only return an intent if the user is clearly asking for that action.\n\n"

                    "If the user is asking a question, requesting information, making conversation, or discussing a topic, return 'none'.\n\n"

                    "Return ONLY intent names."

                    "\nIf multiple actions are requested, return multiple intents separated by commas."

                    "Examples:\n\n"

                    "Open GitHub\n"
                    "-> open_github\n\n"

                    "Can you open GitHub for me?\n"
                    "-> open_github\n\n"

                    "Open GitHub and VS Code\n"
                    "-> open_github,open_vscode\n\n"

                    "Open my coding workspace\n"
                    "-> open_coding_workspace\n\n"

                    "Launch my coding workspace\n"
                    "-> open_coding_workspace\n\n"

                    "Start my coding workspace\n"
                    "-> open_coding_workspace\n\n"

                    "Open my AWS workspace\n"
                    "-> open_aws_workspace\n\n"

                    "Open my school workspace\n"
                    "-> open_school_workspace\n\n"

                    "\nIf no action is requested, return 'none'."

                    "\n\nAvailable intents:"

                    "hello\n"
                    "open_vscode\n"
                    "open_github\n"
                    "open_chatgpt\n"
                    "current_time\n"
                    "remember\n"
                    "recall_memories\n"
                    "search_memory\n"
                    "forget_memory\n"
                    "open_coding_workspace\n"
                    "none"
                ),
            },
            {
                "role": "user",
                "content": command,
            },
        ],
    )

    return response["message"]["content"].strip()