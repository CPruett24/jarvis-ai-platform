from services.capability_response_registry import (
    get_formatter,
    get_registered_formatters,
    register_formatter,
)


def test_register_and_get_formatter():

    def formatter(data):
        return "formatted"

    register_formatter(
        "test_capability",
        formatter,
    )

    result = get_formatter(
        "test_capability"
    )

    assert result is formatter


def test_unknown_formatter_returns_none():

    result = get_formatter(
        "does_not_exist"
    )

    assert result is None


def test_registered_formatters_contains_registered_formatter():

    def formatter(data):
        return "formatted"

    register_formatter(
        "another_capability",
        formatter,
    )

    formatters = get_registered_formatters()

    assert (
        formatters["another_capability"]
        is formatter
    )