from dataclasses import dataclass
import re

from services.capability_registry import (
    get_capability,
)


@dataclass(frozen=True)
class CapabilityRequest:
    """
    Describes a request that appears to target a known
    JARVIS capability.
    """

    capability_name: str
    confidence: float
    matched: bool


@dataclass(frozen=True)
class CapabilityManagementRequest:
    """
    Describes a request to inspect or manage JARVIS'
    capability system.
    """

    action: str = ""
    capability_name: str = ""
    confidence: float = 0.0
    matched: bool = False


CAPABILITY_PATTERNS = {
    # Calendar/email patterns are full-request expressions: a subject mention
    # alone must never imply a request to inspect private/current state.
    "calendar": (
        r"(?:check|show|list|open) (?:me )?(?:my |the )?(?:calendar|schedule|appointments?|events?)(?: today| tomorrow)?",
        r"(?:what is|what's|whats) on my (?:calendar|schedule)(?: today| tomorrow)?",
        r"(?:do i have (?:any )?(?:appointments?|events?)|what do i have scheduled)(?: today| tomorrow)?",
        r"what (?:appointments|events) do i have(?: today| tomorrow)?",
        r"schedule (?:an? )?(?:appointment|event|meeting)(?: .+)?",
    ),
    "email": (
        r"(?:check|show|read|list|open) (?:me )?(?:my |the )?(?:emails?|inbox|mailbox)(?: today)?",
        r"(?:what is|what's|whats) in my (?:inbox|mailbox)",
        r"do i have (?:any )?(?:new |unread )?emails?(?: today)?",
        r"(?:send|draft|write) an? email(?: .+)?",
    ),

    "browser_automation": (
        "browse the web",
        "browse the internet",
        "open a website",
        "go to a website",
        "use the browser",
    ),

    "desktop_automation": (
        "control my computer",
        "control the computer",
        "click on my screen",
        "click something on my screen",
    ),

    "code_review": (
        "review my code",
        "review this code",
        "do a code review",
        "code review",
    ),

    "multi_file_reasoning": (
        "understand the whole project",
        "understand the entire project",
        "understand multiple files",
        "trace across files",
        "trace across multiple files",
        "how do these files work together",
    ),
}


CAPABILITY_MANAGEMENT_PATTERNS = {
    "list": (
        "what can you do",
        "what can you help me with",
        "what capabilities do you have",
        "what are your capabilities",
        "what capabilities are available",
        "what is currently available",
        "what's currently available",
        "what can i use",
    ),

    "list_disabled": (
        "what capabilities are disabled",
        "which capabilities are disabled",
        "what is disabled",
        "what's disabled",
    ),

    "list_unavailable": (
        "what capabilities are unavailable",
        "which capabilities are unavailable",
        "what isn't available",
        "what is unavailable",
        "what's unavailable",
    ),

    "status": (
        "capability status",
        "capabilities status",
        "what is the status of my capabilities",
        "what's the status of my capabilities",
    ),
}

CAPABILITY_DETAIL_PATTERNS = {
    "current_time": (
        "current time",
        "time capability",
    ),

    "hermes_agent": (
        "hermes",
        "hermes agent",
    ),

    "calendar": (
        "calendar",
        "my calendar",
    ),

    "email": (
        "email",
        "emails",
        "my email",
        "my emails",
    ),

    "browser_automation": (
        "browser automation",
        "browser",
    ),

    "desktop_automation": (
        "desktop automation",
        "desktop automation capability",
    ),

    "git_automation": (
        "git automation",
    ),

    "test_automation": (
        "test automation",
    ),

    "code_review": (
        "code review",
    ),

    "multi_file_reasoning": (
        "multi-file understanding",
        "multi file understanding",
    ),

    "planning": (
        "planning capability",
    ),

    "notifications": (
        "notifications capability",
        "notification capability",
    ),

    "daily_briefing": (
        "daily briefing",
    ),
}


def normalize_request(command):
    """
    Normalize natural-language capability requests.
    """

    if not command:
        return ""

    return " ".join(
        command.lower().strip().split()
    ).strip(".,!? ")


def is_capability_explanation(command):
    """Recognize bounded conceptual questions, not requests for current state."""
    subject = r"(?:git branch|git status|calendar|email|code review|(?:coding|aws|school) workspace)"
    normalized = re.sub(r"^(?:can you |could you |please )", "", normalize_request(command))
    return bool(re.fullmatch(
        rf"(?:(?:what is|what's|explain) (?:a |an |the )?{subject}"
        rf"|explain what {subject} does|how does (?:a |an |the )?{subject} work)",
        normalized,
    ))


def detect_capability_management_request(
    command,
):
    """
    Detect deterministic requests to inspect JARVIS'
    capability system.
    """

    normalized = normalize_request(
        command
    )

    if not normalized:
        return CapabilityManagementRequest()

    detail_phrases = (
        "is ",
        "can you use ",
        "why can't you use ",
        "why cant you use ",
        "why can you not use ",
        "tell me about ",
        "what do you know about ",
        "do i have ",
        "do you have ",
        "can you access ",
    )

    is_detail_request = any(
        normalized.startswith(prefix)
        for prefix in detail_phrases
    )

    if is_detail_request:

        for capability_name, patterns in (
            CAPABILITY_DETAIL_PATTERNS.items()
        ):

            for pattern in patterns:

                forms = {
                    f"is {pattern} {state}"
                    for state in ("available", "enabled", "disabled", "unavailable")
                }
                forms.update(f"{prefix}{pattern}" for prefix in detail_phrases if prefix != "is ")
                forms.update(f"{prefix}{pattern} access" for prefix in ("do i have ", "do you have "))
                if normalized in forms:

                    if get_capability(
                        capability_name
                    ) is None:

                        continue

                    return CapabilityManagementRequest(
                        action="details",
                        capability_name=capability_name,
                        confidence=1.0,
                        matched=True,
                    )

    for action, patterns in (
        CAPABILITY_MANAGEMENT_PATTERNS.items()
    ):

        for pattern in patterns:

            if pattern == normalized:

                return CapabilityManagementRequest(
                    action=action,
                    confidence=1.0,
                    matched=True,
                )

    return CapabilityManagementRequest()


def detect_capability_request(command):
    """
    Detect whether a request clearly targets a registered
    high-level capability.

    This is intentionally deterministic and conservative.
    """

    normalized = normalize_request(command)

    normalized = re.sub(r"^(?:can you |could you |please )", "", normalized)

    if not normalized:
        return CapabilityRequest(
            capability_name="",
            confidence=0.0,
            matched=False,
        )

    for capability_name, patterns in CAPABILITY_PATTERNS.items():

        for pattern in patterns:

            if capability_name in {"calendar", "email"}:
                matched = re.fullmatch(pattern, normalized) is not None
            else:
                matched = normalized == pattern or normalized.startswith(pattern + " ")

            if matched:

                capability = get_capability(
                    capability_name
                )

                if capability is None:
                    continue

                return CapabilityRequest(
                    capability_name=capability_name,
                    confidence=1.0,
                    matched=True,
                )

    return CapabilityRequest(
        capability_name="",
        confidence=0.0,
        matched=False,
    )

@dataclass(frozen=True)
class AgentRequest:
    """
        Describes a request that should be delegated to an
        external JARVIS agent.
    """
    agent_name: str = ""
    task: str = ""
    confidence: float = 0.0
    matched: bool = False
    

AGENT_PATTERNS = (
    "research ",
    "research this",
    "research that",
    "look into ",
    "investigate ",
    "investigate this",
    "investigate that",
    "analyze this project",
    "analyze the project",
    "analyze my project",
    "analyze these files",
    "analyze the files",
    "work through this",
    "work through these files",
    "figure out why ",
    "find out why ",
    "find out how ",
    "look up ",
    "search the web for ",
    "search the internet for ",
    "browse the web for ",
    "browse the internet for ",
)


def detect_agent_request(
    command,
):
    """
    Detect requests appropriate for delegation to an
    external agent.

    Matching is intentionally conservative. Simple commands,
    deterministic capabilities, and ordinary conversation
    should not automatically be sent to Hermes.
    """

    normalized = normalize_request(
        command
    )

    if not normalized:
        return AgentRequest()

    for pattern in AGENT_PATTERNS:

        if normalized.startswith(pattern):

            task = normalized[
                len(pattern):
            ].strip()

            # Remove common connector words between the
            # Hermes request and the actual task.
            for prefix in (
                "to ",
                "for ",
                "and ",
                "please ",
            ):

                if task.startswith(prefix):

                    task = task[
                        len(prefix):
                    ].strip()

            if not task:

                return AgentRequest()

            return AgentRequest(
                agent_name="hermes",
                task=task,
                confidence=1.0,
                matched=True,
            )

    return AgentRequest()
