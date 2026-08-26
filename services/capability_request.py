from dataclasses import dataclass

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
    "calendar": (
        "calendar",
        "schedule",
        "appointments",
        "appointment",
        "events",
        "event",
        "what's on my calendar",
        "whats on my calendar",
        "what is on my calendar",
    ),

    "email": (
        "email",
        "emails",
        "inbox",
        "mailbox",
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

                if pattern in normalized:

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

            if pattern in normalized:

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

    if not normalized:
        return CapabilityRequest(
            capability_name="",
            confidence=0.0,
            matched=False,
        )

    for capability_name, patterns in CAPABILITY_PATTERNS.items():

        for pattern in patterns:

            if pattern in normalized:

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