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