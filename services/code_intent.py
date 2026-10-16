import re


def is_conversation_summary_phrase(command):
    """Conversation phrases (including truncated speech) aren't filenames.

    Full matching preserves explicit targets such as 'our last.py'.
    """
    text = " ".join(command.lower().split()).rstrip(".!?")
    if re.fullmatch(
        r"(?:can you |could you |please )?(?:summarize|summarise|summarizing) "
        r"our(?: (?:last|previous))?(?: (?:conversation|discussion))?",
        text,
    ):
        return True
    # Only explicit cutoff markers on prefixes of conversation words qualify.
    # Extensions, paths and arbitrary hyphenated names remain file targets.
    match = re.fullmatch(
        r"(?:can you |could you |please )?(?:summarize|summarise|summarizing) "
        r"our(?: (?:last|previous))? ([a-z]+)[-–—]", text,
    )
    return bool(match and any(word.startswith(match[1]) for word in (
        "last", "previous", "conversation", "discussion")))


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


def should_use_file_context(command, topic=None):
    """Require file evidence or a follow-up to the current file discussion."""
    from services.conversation_manager import get_topic, is_file_discussion_active

    topic = get_topic() if topic is None else topic
    if not topic or topic.get("type") != "file":
        return False
    text = command.lower().strip().rstrip(".!?")
    filename = topic["filename"].lower().replace("\\", "/")
    if re.search(r"(?<![\w.])" + re.escape(filename.split("/")[-1]) + r"(?![\w.])", text):
        return True
    if re.search(r"\b(?:this|that|its) (?:code|file|function|method|class|variable|imports?|implementation)\b", text) or re.search(
        r"\bthe (?:code|file|imports?|implementation)\b", text
    ):
        return True
    if re.search(r"\b\w+\(\)", text) or re.search(r"`[^`]+`", text):
        return True
    if not is_file_discussion_active():
        return False
    if text in {"tell me more", "explain that", "explain it", "why", "how so", "go on", "continue"}:
        return True
    return bool(is_contextual_code_question(text) or (
        is_code_question(text) and re.search(r"\b(?:this|that|it|here)\b", text)
    ))


def is_clear_new_question(command):
    """Recognizable standalone questions may supersede filename clarification."""
    return bool(re.match(
        r"^(?:what (?:is|are)|who (?:is|are)|where (?:is|are)|when (?:is|does)|"
        r"how (?:does|do|is|are)|why (?:is|are|does|do))\s+\S+",
        command.lower().strip(),
    ))
