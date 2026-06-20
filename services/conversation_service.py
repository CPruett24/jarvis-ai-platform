conversation_history = []

def add_user_message(message):
    conversation_history.append({"role": "user", "content": message})

def add_assistant_message(message):
    conversation_history.append({"role": "assistant", "content": message})

def get_conversation_history():
    return conversation_history

def get_history():
    return conversation_history[-10:]  # Return the last 10 messages for context

def clear_history():    
    conversation_history.clear()