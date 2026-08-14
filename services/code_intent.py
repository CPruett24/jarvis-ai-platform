CODE_PATTERNS = [
    "why",
    "how",
    "what does",
    "what is",
    "would you",
    "should",
    "could",
    "is there",
    "can this",
    "what happens",
]


def is_code_question(command):

    command = command.lower().strip()

    return any(
        command.startswith(pattern)
        for pattern in CODE_PATTERNS
    )

def is_contextual_code_question(command):

    command = command.lower().strip()

    contextual_phrases = {
        "would you keep",
        "what would you change",
        "what would you do",
        "what should i change",
        "what should we change",
        "what would you improve",
        "how would you improve",
        "what do you think",
        "what do you recommend",
        "what would you recommend",
        "what would you do differently",
        "what should be changed",
        "what would be better",
        "is this a good design",
        "is this design good",
        "how could this be improved",
        "how could this improve",
    }

    return any(
        phrase in command
        for phrase in contextual_phrases
    )