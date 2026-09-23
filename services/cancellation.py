"""Cooperative operation cancellation using caller-owned threading.Event signals.

Use a fresh event for each operation. Setting it requests cancellation; work
acknowledges it at checkpoints by raising OperationCancelled. This cannot stop
a blocking call or remote work unless that operation explicitly cooperates.
"""


class OperationCancelled(Exception):
    """Local cooperative work acknowledged cancellation, not success or failure."""


def check_cancelled(cancellation_event=None):
    if cancellation_event is not None and cancellation_event.is_set():
        raise OperationCancelled("Local operation cancelled.")
