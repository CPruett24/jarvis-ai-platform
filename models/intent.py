from dataclasses import dataclass, field


@dataclass
class Intent:
    """
    Represents JARVIS's interpretation of a user command.

    type:
        The broad category of the request.

    confidence:
        How confident the resolver is in the classification.

    tool_request:
        A ToolRequest when the intent maps directly to a tool.

    metadata:
        Additional context used by downstream capabilities.
    """

    type: str
    confidence: float = 1.0
    tool_request: object = None
    metadata: dict = field(default_factory=dict)