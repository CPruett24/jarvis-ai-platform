from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """
    Describes a capability JARVIS knows about.

    A capability can be registered even when it is not
    currently available for execution.
    """

    name: str
    description: str
    category: str
    available: bool = False
    tool_name: str | None = None
    reason: str | None = None


CAPABILITY_REGISTRY = {
    # =========================================================
    # CORE / CURRENTLY AVAILABLE
    # =========================================================

    "current_time": Capability(
        name="Current Time",
        description="Get the current local time.",
        category="system",
        available=True,
        tool_name="current_time",
    ),

    "git_status": Capability(
        name="Git Status",
        description="Get the current Git repository status.",
        category="development",
        available=True,
        tool_name="git_status",
    ),

    "git_branch": Capability(
        name="Git Branch",
        description="Get the current Git branch.",
        category="development",
        available=True,
        tool_name="git_branch",
    ),

    "git_remote": Capability(
        name="Git Remote",
        description="List configured Git remotes.",
        category="development",
        available=True,
        tool_name="git_remote",
    ),

    "project_search": Capability(
        name="Project Search",
        description="Search the current project for text.",
        category="development",
        available=True,
        tool_name="search_project",
    ),

    "file_search": Capability(
        name="File Search",
        description="Find files within the current project.",
        category="development",
        available=True,
        tool_name="find_file",
    ),

    "file_summary": Capability(
        name="File Summary",
        description="Summarize a project file.",
        category="development",
        available=True,
        tool_name="summarize_file",
    ),

    "code_explanation": Capability(
        name="Code Explanation",
        description="Explain the purpose and behavior of source code files.",
        category="development",
        available=True,
        tool_name="explain_file",
    ),

    "project_tree": Capability(
        name="Project Structure",
        description="Show the structure of the current project.",
        category="development",
        available=True,
        tool_name="project_tree",
    ),

    "workspace_management": Capability(
        name="Workspace Management",
        description="Open configured development workspaces.",
        category="development",
        available=True,
    ),

    "memory": Capability(
        name="Memory",
        description="Remember, recall, search, and forget stored information.",
        category="personal",
        available=True,
    ),

    # =========================================================
    # REGISTERED BUT NOT YET AVAILABLE
    # =========================================================

    "calendar": Capability(
        name="Calendar",
        description="Read and manage calendar events.",
        category="personal",
        available=False,
        reason="Calendar integration has not been configured yet.",
    ),

    "email": Capability(
        name="Email",
        description="Read, draft, and manage email.",
        category="personal",
        available=False,
        reason="Email integration has not been configured yet.",
    ),

    "browser_automation": Capability(
        name="Browser Automation",
        description="Interact with websites and perform browser-based tasks.",
        category="automation",
        available=False,
        reason="Browser automation has not been implemented yet.",
    ),

    "desktop_automation": Capability(
        name="Desktop Automation",
        description="Control desktop applications and perform computer actions.",
        category="automation",
        available=False,
        reason="Desktop automation has not been implemented yet.",
    ),

    "git_automation": Capability(
        name="Git Automation",
        description="Create commits, branches, pull requests, and perform other Git actions.",
        category="development",
        available=False,
        reason="Git write operations have not been enabled yet.",
    ),

    "test_automation": Capability(
        name="Test Automation",
        description="Run tests and analyze test results.",
        category="development",
        available=False,
        reason="Test execution capability has not been exposed to JARVIS yet.",
    ),

    "code_review": Capability(
        name="Code Review",
        description="Review source code for bugs, code smells, and improvement opportunities.",
        category="development",
        available=False,
        reason="Full code review capability has not been implemented yet.",
    ),

    "multi_file_reasoning": Capability(
        name="Multi-File Understanding",
        description="Reason across multiple source files and trace relationships between them.",
        category="development",
        available=False,
        reason="Multi-file reasoning is a future development capability.",
    ),

    "planning": Capability(
        name="Planning",
        description="Create and manage multi-step plans for projects and tasks.",
        category="productivity",
        available=False,
        reason="Advanced autonomous planning is still under development.",
    ),

    "notifications": Capability(
        name="Notifications",
        description="Send reminders and notifications.",
        category="personal",
        available=False,
        reason="Notification delivery has not been configured yet.",
    ),

    "daily_briefing": Capability(
        name="Daily Briefing",
        description="Generate a personalized briefing using connected information sources.",
        category="personal",
        available=False,
        reason="The required external integrations are not configured yet.",
    ),
}


def get_capability(name):
    """
    Return a registered capability by name.
    """

    return CAPABILITY_REGISTRY.get(name)


def capability_exists(name):
    """
    Return True when a capability is registered.
    """

    return name in CAPABILITY_REGISTRY


def is_capability_available(name):
    """
    Return True when a registered capability is currently executable.
    """

    capability = get_capability(name)

    if capability is None:
        return False

    return capability.available


def get_available_capabilities():
    """
    Return all currently available capabilities.
    """

    return {
        name: capability
        for name, capability in CAPABILITY_REGISTRY.items()
        if capability.available
    }


def get_unavailable_capabilities():
    """
    Return registered capabilities that are not currently available.
    """

    return {
        name: capability
        for name, capability in CAPABILITY_REGISTRY.items()
        if not capability.available
    }


def get_capability_status(name):
    """
    Return a human-readable status for a capability.
    """

    capability = get_capability(name)

    if capability is None:
        return "This capability is not registered."

    if capability.available:
        return (
            f"{capability.name} is available."
        )

    reason = capability.reason or (
        "This capability is not currently available."
    )

    return (
        f"{capability.name} is registered but unavailable. "
        f"{reason}"
    )