"""Source retrieval contracts. A successful read is not a verified interpretation."""
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
import math


class RetrievalStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    DENIED = "denied"
    READ_ERROR = "read_error"
    UNSUPPORTED = "unsupported"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    STALE = "stale"


@dataclass(frozen=True)
class RetrievalLimits:
    max_entries: int = 10000
    max_file_bytes: int = 512 * 1024
    max_search_bytes: int = 16 * 1024 * 1024
    max_excerpts: int = 8
    max_lines: int = 120
    max_evidence_bytes: int = 64 * 1024
    seconds: float = 3.0

    def __post_init__(self):
        if (any(type(value) is not int or value <= 0 for key, value in self.__dict__.items() if key != "seconds")
                or not isinstance(self.seconds, (int, float)) or not math.isfinite(self.seconds) or self.seconds <= 0):
            raise ValueError("Retrieval limits must be positive.")


@dataclass(frozen=True)
class SourceExcerpt:
    source_id: str
    project_id: str
    revision: int
    path: str
    start_line: int
    end_line: int
    text: str
    retrieved_at: str
    signature: tuple
    digest: str
    truncated: bool = False
    kind: str = "source"
    total_lines: int = 0

    def __post_init__(self):
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("Source ranges are inclusive and one-based.")
        if len(self.text.split("\n")) != self.end_line - self.start_line + 1:
            raise ValueError("Source text does not match its range.")


@dataclass
class RetrievalResult:
    project_id: str
    revision: int
    operation: str
    status: RetrievalStatus
    excerpts: list[SourceExcerpt] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    limits_reached: list[str] = field(default_factory=list)
    error: str = ""
    entries_visited: int = 0
    bytes_read: int = 0
    request_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def success(self):
        return self.status in (RetrievalStatus.SUCCESS, RetrievalStatus.PARTIAL)
