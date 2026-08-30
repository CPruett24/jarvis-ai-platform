from services.conversation_db import (
    save_message,
    get_recent_messages,
)

conversation_history = []

def restore_recent_history(
    limit=10,
):

    messages = get_recent_messages(
        limit=limit
    )

    conversation_history.clear()

    for message in messages:

        conversation_history.append(
            {
                "role": message["role"],
                "content": message["content"],
            }
        )

def add_message(role, message):

    entry = {
        "role": role,
        "content": message
    }

    conversation_history.append(entry)

    try:
        save_message(role, message)

    except Exception as e:
        print(f"Conversation save failed: {e}")


def get_conversation_history():
    return conversation_history


def get_history():
    return conversation_history[-10:]


def clear_history():
    conversation_history.clear()