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
                "source": message.get("source"),
            }
        )

def add_message(
    role,
    message,
    source=None,
):

    entry = {
        "role": role,
        "content": message,
        "source": source,
    }

    conversation_history.append(entry)

    try:
        save_message(
            role,
            message,
            source=source,
        )

    except Exception as e:
        print(f"Conversation save failed: {e}")


def get_conversation_history():
    return conversation_history


def get_history():
    return conversation_history[-10:]

def get_source_aware_history(
    limit=10,
):

    history = conversation_history[
        -limit:
    ]

    formatted_history = []

    for message in history:

        role = message["role"]
        content = message["content"]
        source = message.get("source")

        if source == "hermes":

            content = (
                "Hermes research result:\n"
                f"{content}"
            )

        elif source == "router":

            content = (
                "JARVIS system response:\n"
                f"{content}"
            )

        elif source and source not in (
            "user",
            "ollama",
        ):

            content = (
                f"External source ({source}) result:\n"
                f"{content}"
            )

        formatted_history.append(
            {
                "role": role,
                "content": content,
            }
        )

    return formatted_history

def clear_history():
    conversation_history.clear()