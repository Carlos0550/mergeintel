"""Provider-agnostic AI client interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass(slots=True)
class AIMessage:
    """Structured chat message for provider adapters."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass(slots=True)
class ToolDefinition:
    """Provider-agnostic tool schema."""

    name: str
    description: str
    parameters: dict


@dataclass(slots=True)
class ToolCall:
    """A tool invocation requested by the AI."""

    id: str
    name: str
    arguments: dict


# --- Stream events ---


@dataclass(slots=True)
class StreamEvent:
    """Base class for streaming events."""


@dataclass(slots=True)
class TextChunkEvent(StreamEvent):
    """Partial text from the AI."""

    text: str


@dataclass(slots=True)
class ToolCallEvent(StreamEvent):
    """The AI wants to execute one or more tools."""

    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(slots=True)
class DoneEvent(StreamEvent):
    """Stream finished."""


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

    @abstractmethod
    async def stream_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> AsyncIterator[str]:
        """Stream a text completion from structured messages."""

    async def stream_text_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[ToolDefinition],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncIterator[StreamEvent]:
        """Stream with tool-use support. Default falls back to plain streaming."""
        async for chunk in self.stream_text(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield TextChunkEvent(text=chunk)
        yield DoneEvent()

    async def aclose(self) -> None:
        """Release provider resources when required."""
