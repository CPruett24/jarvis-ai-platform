from models.information import (
    InformationItem,
    InformationSource,
)


def create_information_item(
    content,
    source,
):

    return InformationItem(
        content=content,
        source=source,
    )


def create_memory_information(
    content,
):

    return create_information_item(
        content,
        InformationSource.REMEMBERED,
    )


def format_information_context(
    items,
):

    if not items:

        return ""

    lines = []

    for item in items:

        lines.append(
            f"[{item.source.value}] "
            f"{item.content}"
        )

    return "\n".join(
        lines
    )

def create_observed_information(
    content,
):

    return create_information_item(
        content,
        InformationSource.OBSERVED,
    )