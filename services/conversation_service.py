from services.conversation_db import save_message

conversation_history = []


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