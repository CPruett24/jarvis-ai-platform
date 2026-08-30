from models.information import (
    InformationSource,
)

from services.grounding_service import (
    create_information_item,
    create_memory_information,
    format_information_context,
)

def test_create_information_item():

    item = create_information_item(
        "The user said hello.",
        InformationSource.USER_PROVIDED,
    )

    assert (
        item.content
        == "The user said hello."
    )

    assert (
        item.source
        == InformationSource.USER_PROVIDED
    )


def test_format_information_context():

    first_item = create_information_item(
        "The user asked about AI.",
        InformationSource.USER_PROVIDED,
    )

    second_item = create_information_item(
        "A memory was retrieved.",
        InformationSource.REMEMBERED,
    )

    context = format_information_context(
        [
            first_item,
            second_item,
        ]
    )

    assert (
        context
        == (
            "[user_provided] "
            "The user asked about AI.\n"
            "[remembered] "
            "A memory was retrieved."
        )
    )


def test_format_information_context_empty():

    context = format_information_context(
        []
    )

    assert context == ""

def test_create_memory_information():

    item = create_memory_information(
        "Your project deadline is Friday."
    )

    assert (
        item.content
        == "Your project deadline is Friday."
    )

    assert (
        item.source
        == InformationSource.REMEMBERED
    )