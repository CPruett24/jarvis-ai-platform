import re


def relationship_target(text):
    """Syntax only; exact identities are resolved by canonical analysis later."""
    text = text.strip().strip("`\"'")
    if "::" in text:
        filename, qualified_name = text.split("::", 1)
        return {"filename": filename, "qualified_name": qualified_name}
    return {"filename": text} if text.endswith(".py") else {"qualified_name": text}


def resolve_relationship_request(command):
    """Explicit relationship grammar; case-insensitive verbs, case-preserved targets."""
    text = command.strip().rstrip(".!?")
    patterns = (
        (r"(?:what|who) calls (.+)", "calls", "reverse"),
        (r"(?:what|which functions) does (.+) call", "calls", "forward"),
        (r"(?:what|which files) (?:depends? on|imports?) (.+)", "imports", "reverse"),
        (r"what does (.+) (?:import|depend on)", "imports", "forward"),
        (r"(?:import )?dependencies of (.+)", "imports", "forward"),
        (r"what (?:could|would) be affected if i (?:change|modify) (.+)", "impact", "reverse"),
        (r"(?:potential )?impact of (?:changing )?(.+)", "impact", "reverse"),
    )
    for pattern, operation, direction in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            return {"operation": operation, "direction": direction, "depth": 2,
                    **relationship_target(match[1])}
    match = re.fullmatch(r"trace (.+?)(?: (forward|reverse))?(?: (?:to |for )?(\d+) levels?)?", text, re.I)
    if match:
        return {"operation": "trace", "direction": (match[2] or "forward").lower(),
                "depth": int(match[3]) if match[3] else 2, **relationship_target(match[1])}
    match = re.fullmatch(r"how do (.+?) and (.+?) connect", text, re.I)
    if match:
        return {"operation": "connections", "direction": "forward", "depth": 2,
                "comparison": relationship_target(match[2]), **relationship_target(match[1])}
    return None


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


def resolve_source_request(command):
    """Bounded deterministic C1 requests; conceptual questions stay conversational."""
    text = command.strip().rstrip(".!?")
    normalized = re.sub(r"^(?:can you |could you |please )", "", text, flags=re.I)
    if normalized.lower() in {"list authorized projects", "what projects can you read", "show authorized projects"}:
        return {"question": text, "operation": "projects"}
    selection = re.fullmatch(r"(?:select|use) project ([\w-]+)", normalized, re.I)
    if selection:
        return {"question": text, "operation": "select", "selection_id": selection[1]}
    direct = re.fullmatch(r"(?:read|show) (?:the )?(?:file )?(.+)", normalized, re.I)
    if direct and re.search(r"[./\\]", direct[1]):
        return {"question": text, "filename": direct[1], "operation": "excerpt"}
    if re.fullmatch(r"explain (?:the )?router", normalized, re.I):
        return {"question": text, "filename": "router", "operation": "read"}
    if is_conversation_summary_phrase(normalized):
        return None
    if re.match(r"^(?:summarize|summarise|summarizing)\b", normalized, re.I):
        return None  # Existing parser/tool path now executes the C1 capability.
    if re.match(r"^(?:what about|how about|switch to|now explain|next explain)\b", normalized, re.I):
        return None  # Existing deterministic topic-transition path owns these.
    if re.fullmatch(r"(?:analyze|investigate) (?:these|the|my) files", normalized, re.I):
        return {"question": text, "operation": "read"}
    # Request framing is independent of the project subject. Keep the original
    # question for retrieval, and recognize wrappers before any generic/agent
    # routing. A bare mention of 'project', 'file' or an indefinite router isn't
    # sufficient evidence of a request to inspect the user's code.
    inquiry = r"(?:explain|describe|analyze|investigate|research|what|how|why|where|which|show|list|tell me|show me|find out|figure out|look into|walk me through|help me understand)\b"
    if re.search(r"\b(?:this|my|the|our) project\b", normalized, re.I) and re.match(
            "^" + inquiry, normalized, re.I) and not re.search(
                r"\bproject (?:management|manager|planning|proposal|based learning)\b", normalized, re.I):
        if re.match(r"^(?:what files|show|list)\b", normalized, re.I) and re.search(r"\b(?:files|structure|tree)\b", normalized, re.I):
            return {"question": text, "operation": "list",
                    "recursive": bool(re.search(r"\b(?:all|recursive|recursively)\b", normalized, re.I))}
        return {"question": text, "operation": "search"}
    component = re.match(
        r"^(?:" + inquiry + r"\s+(?:how|why)|(?:how|why)\s+(?:does|do)) (?:the|our) "
        r"(?P<subject>(?:[a-z_]+ ){0,3}(?:router|parser|dispatcher|controller|handler|service|module|cache|index)) "
        r"(?:handles?|routes?|processes?|stores?|loads?|saves?|dispatches?|selects?|resolves?|reads?|writes?)\b",
        normalized, re.I,
    )
    if component and not re.search(r"\b(?:network|wireless|wifi|wi-fi|packets?|internet traffic)\b", normalized, re.I):
        return {"question": text, "filename": component["subject"], "operation": "read"}
    match = re.fullmatch(r"what does (?:the )?([\w./\\:-]+)(?: do)?", normalized, re.I)
    if match:
        return {"question": text, "filename": match[1], "operation": "read"}
    # Explicit filenames inside standalone code questions must not become guesses.
    match = re.search(r"(?<![\w.])([\w./\\:-]+\.(?:py|js|ts|tsx|jsx|rs|go|md|txt|json|yaml|yml|toml))(?!\w)", normalized, re.I)
    if match and re.match(r"^(?:what|how|why|describe|research|investigate|analyze|look into|figure out why|find out why|find out how)\b", normalized, re.I):
        return {"question": text, "filename": match[1], "operation": "read"}
    return None
