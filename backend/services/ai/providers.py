"""Concrete AI provider adapters."""

from __future__ import annotations

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from backend.services.ai.base import AIMessage, AIProviderClient


class AnthropicAIProvider(AIProviderClient):
    """Anthropic adapter using the official async SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        system_prompt = "\n\n".join(message.content for message in messages if message.role == "system").strip()
        user_messages = [
            {"role": "user" if message.role == "system" else message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]
        if not user_messages:
            user_messages = [{"role": "user", "content": "Respond to the provided system instructions."}]

        response = await self._client.messages.create(
            model=self.model,
            system=system_prompt or None,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", "")
            if text:
                parts.append(text)
        return "\n".join(parts).strip()

    async def aclose(self) -> None:
        await self._client.close()


class OpenAICompatibleAIProvider(AIProviderClient):
    """Adapter for providers that speak the OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model=model)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": message.role, "content": message.content} for message in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            return "\n".join(str(item) for item in content).strip()
        return (content or "").strip()

    async def aclose(self) -> None:
        await self._client.close()
