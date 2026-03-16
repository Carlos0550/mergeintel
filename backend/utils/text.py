"""Text formatting helpers."""

from __future__ import annotations


def capitalize_words(value: str) -> str:
    """Capitalize each word in a string while normalizing extra spaces."""

    normalized = " ".join(value.split())
    if not normalized:
        return ""
    return " ".join(word.capitalize() for word in normalized.split(" "))
