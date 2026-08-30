import re


def clean_agent_response(
    text,
    max_length=1200,
):
    """
    Clean an external agent response for text-to-speech.

    Removes Markdown formatting, citation markers, URLs,
    and excessive whitespace while preserving the actual
    research content.
    """

    if not text:
        return ""

    cleaned = str(text)

    # Remove Markdown headings.
    cleaned = re.sub(
        r"(?m)^#{1,6}\s*",
        "",
        cleaned,
    )

    # Remove bold and italic markers.
    cleaned = cleaned.replace(
        "**",
        "",
    )

    cleaned = cleaned.replace(
        "__",
        "",
    )

    cleaned = cleaned.replace(
        "*",
        "",
    )

    cleaned = cleaned.replace(
        "_",
        "",
    )

    # Remove Markdown links while preserving link text.
    cleaned = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        cleaned,
    )

    # Remove numbered citation markers such as [1] or [1][2].
    cleaned = re.sub(
        r"\[\d+\]",
        "",
        cleaned,
    )

    # Remove URLs.
    cleaned = re.sub(
        r"https?://\S+",
        "",
        cleaned,
    )

    # Remove source sections.
    cleaned = re.sub(
        r"(?is)\bSources\s*:?.*$",
        "",
        cleaned,
    )

    # Normalize whitespace.
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    if max_length and len(cleaned) > max_length:

        # Reserve room for the ellipsis so the final
        # response never exceeds max_length.
        if max_length <= 3:

            cleaned = cleaned[:max_length]

        else:

            truncated = cleaned[
                :max_length - 3
            ]

            # Prefer ending at a sentence boundary.
            sentence_end = max(
                truncated.rfind("."),
                truncated.rfind("!"),
                truncated.rfind("?"),
            )

            if sentence_end > (
                (max_length - 3) * 0.6
            ):

                truncated = truncated[
                    :sentence_end + 1
                ]

            else:

                truncated = (
                    truncated.rstrip()
                    + "..."
                )

            cleaned = truncated

    return cleaned