"""Explicit playback results. Completion is not proof of human receipt."""
from enum import Enum


class PlaybackOutcome(str, Enum):
    UNKNOWN = "unknown"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    SKIPPED = "skipped"


def playback_outcome(value):
    # Legacy providers returning None cannot prove successful playback.
    return value if isinstance(value, PlaybackOutcome) else PlaybackOutcome.UNKNOWN
