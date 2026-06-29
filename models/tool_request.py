from dataclasses import dataclass, field


@dataclass
class ToolRequest:

    tool: str

    arguments: dict = field(default_factory=dict)