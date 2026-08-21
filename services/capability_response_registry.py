_FORMATTERS = {}


def register_formatter(
    capability_name,
    formatter,
):
    """
    Register a response formatter for a capability.
    """

    if not capability_name:
        raise ValueError(
            "Capability name is required."
        )

    if not callable(formatter):
        raise TypeError(
            "Formatter must be callable."
        )

    _FORMATTERS[
        capability_name
    ] = formatter


def get_formatter(
    capability_name,
):
    """
    Return the formatter registered for a capability.
    """

    return _FORMATTERS.get(
        capability_name
    )


def get_registered_formatters():
    """
    Return all registered response formatters.
    """

    return dict(
        _FORMATTERS
    )


def clear_formatters():
    """
    Clear registered formatters.

    Intended primarily for testing.
    """

    _FORMATTERS.clear()