"""Provider-agnostic AI client interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class AIMessage:
    """Structured chat message for provider adapters."""

    role: str
    content: str


class AIProviderClient(ABC):
    """Small provider-agnostic surface used by summary and chat services."""

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def generate_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        """Generate a text completion from structured messages."""

    async def aclose(self) -> None:
        """Release provider resources when required."""

