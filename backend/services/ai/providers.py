"""Concrete AI provider adapters."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from backend.services.ai.base import (
    AIMessage,
    AIProviderClient,
    DoneEvent,
    StreamEvent,
    TextChunkEvent,
    ToolCall,
    ToolCallEvent,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


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

    async def stream_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> AsyncIterator[str]:
        system_prompt = "\n\n".join(message.content for message in messages if message.role == "system").strip()
        user_messages = [
            {"role": "user" if message.role == "system" else message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]
        if not user_messages:
            user_messages = [{"role": "user", "content": "Respond to the provided system instructions."}]

        async with self._client.messages.stream(
            model=self.model,
            system=system_prompt or None,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

    async def stream_text_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[ToolDefinition],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncIterator[StreamEvent]:
        if not tools:
            async for evt in super().stream_text_with_tools(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens
            ):
                yield evt
            return

        system_prompt = "\n\n".join(
            m.content for m in messages if m.role == "system"
        ).strip()
        api_messages = self._build_anthropic_messages(messages)
        tools_anthropic = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

        async with self._client.messages.stream(
            model=self.model,
            system=system_prompt or None,
            messages=api_messages,
            tools=tools_anthropic,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            current_tool_name: str | None = None
            current_tool_id: str | None = None
            input_json_parts: list[str] = []
            pending_tool_calls: list[ToolCall] = []

            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        input_json_parts = []
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta" and delta.text:
                        yield TextChunkEvent(text=delta.text)
                    elif delta.type == "input_json_delta":
                        input_json_parts.append(delta.partial_json)
                elif event.type == "content_block_stop":
                    if current_tool_name and current_tool_id is not None:
                        raw = "".join(input_json_parts)
                        try:
                            parsed = json.loads(raw) if raw else {}
                            args = parsed if isinstance(parsed, dict) else {}
                        except json.JSONDecodeError:
                            args = {}
                        pending_tool_calls.append(
                            ToolCall(id=current_tool_id, name=current_tool_name, arguments=args)
                        )
                        current_tool_name = None
                        current_tool_id = None
                        input_json_parts = []
                elif event.type == "message_stop":
                    break

            if pending_tool_calls:
                yield ToolCallEvent(tool_calls=pending_tool_calls)

        yield DoneEvent()

    @staticmethod
    def _build_anthropic_messages(messages: list[AIMessage]) -> list[dict]:
        """Convert AIMessage list to Anthropic API message format."""
        result: list[dict] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool" and m.tool_call_id:
                result.append({
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                    ],
                })
            elif m.role == "assistant" and m.tool_calls:
                content_blocks: list[dict] = []
                if m.content:
                    content_blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                result.append({"role": "assistant", "content": content_blocks})
            else:
                role = "user" if m.role == "system" else m.role
                result.append({"role": role, "content": m.content})
        if not result:
            result.append({"role": "user", "content": "Respond to the provided system instructions."})
        return result

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
        self._base_url = base_url

    @property
    def supports_tools(self) -> bool:
        """Heuristic: OpenAI and Groq support tools; Ollama depends on local model."""
        if self._base_url is None:
            return True  # default OpenAI
        url = self._base_url.lower()
        if "groq" in url or "openai" in url:
            return True
        return False

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

    async def stream_text(
        self,
        messages: list[AIMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": message.role, "content": message.content} for message in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if isinstance(delta, str):
                if delta:
                    yield delta
                continue
            if isinstance(delta, list):
                for item in delta:
                    text = getattr(item, "text", None)
                    if text:
                        yield text

    async def stream_text_with_tools(
        self,
        messages: list[AIMessage],
        *,
        tools: list[ToolDefinition],
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> AsyncIterator[StreamEvent]:
        if not tools or not self.supports_tools:
            async for evt in super().stream_text_with_tools(
                messages, tools=[], temperature=temperature, max_tokens=max_tokens
            ):
                yield evt
            return

        api_messages = self._build_openai_messages(messages)
        tools_openai = [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
            }
            for t in tools
        ]

        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            tools=tools_openai,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        tool_calls_acc: dict[int, dict] = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextChunkEvent(text=delta.content)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc_delta.id or "", "name": "", "arguments": ""}
                    acc = tool_calls_acc[idx]
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            acc["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            acc["arguments"] += tc_delta.function.arguments

        if tool_calls_acc:
            calls: list[ToolCall] = []
            for idx in sorted(tool_calls_acc):
                acc = tool_calls_acc[idx]
                try:
                    parsed = json.loads(acc["arguments"]) if acc["arguments"] else {}
                    args = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    args = {}
                calls.append(ToolCall(
                    id=acc["id"] or f"tool_call_{idx}",
                    name=acc["name"],
                    arguments=args,
                ))
            yield ToolCallEvent(tool_calls=calls)

        yield DoneEvent()

    @staticmethod
    def _build_openai_messages(messages: list[AIMessage]) -> list[dict]:
        """Convert AIMessage list to OpenAI API message format."""
        result: list[dict] = []
        for m in messages:
            if m.role == "tool" and m.tool_call_id:
                result.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
            elif m.role == "assistant" and m.tool_calls:
                # OpenAI-compatible providers are more reliable when tool-call assistant
                # messages are sent back without free-form content.
                msg: dict = {"role": "assistant", "content": None}
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ]
                result.append(msg)
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    async def aclose(self) -> None:
        await self._client.close()
