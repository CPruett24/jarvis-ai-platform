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

# Natural-language phrases associated with registered
# capabilities that are not yet deterministic commands.
#
# These are intentionally conservative. We do not want
# ordinary conversation accidentally becoming a capability
# request.

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


def normalize_request(command):
    """
    Normalize natural-language capability requests.
    """

    if not command:
        return ""

    return " ".join(
        command.lower().strip().split()
    ).strip(".,!? ")


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