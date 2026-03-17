"""Reusable helpers for AI context preparation."""

from __future__ import annotations

from backend.services.ai import AIMessage


def truncate_text(value: str | None, *, limit: int = 8_000) -> str:
    """Bound large context strings before persisting or sending them to providers."""

    normalized = (value or "").strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}\n\n... [truncated]"


def build_messages(*, system_prompt: str | None = None, user_prompt: str) -> list[AIMessage]:
    """Create a provider-agnostic chat message list."""

    messages: list[AIMessage] = []
    if system_prompt:
        messages.append(AIMessage(role="system", content=system_prompt))
    messages.append(AIMessage(role="user", content=user_prompt))
    return messages
