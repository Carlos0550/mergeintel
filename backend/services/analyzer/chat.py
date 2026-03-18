"""Chat context builder powered by the unified AI provider."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from backend.services.ai import AIProviderClient
from backend.services.ai.base import AIMessage, DoneEvent, TextChunkEvent, ToolCallEvent
from backend.services.ai.tools import TOOL_DEFINITIONS, ToolContext, execute_tool
from backend.services.analyzer.helpers import build_messages
from backend.services.analyzer.prompts import CHAT_SYSTEM_PROMPT_WITH_TOOLS, build_chat_context

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 5


class AnalysisChatService:
    """Build contextual answers from persisted PR analyses."""

    def __init__(self, ai_client: AIProviderClient) -> None:
        self.ai_client = ai_client

    async def answer(
        self,
        *,
        analysis_summary: str,
        checklist_lines: list[str],
        file_lines: list[str],
        history_lines: list[str],
        user_message: str,
    ) -> str:
        prompt = build_chat_context(
            analysis_summary=analysis_summary,
            checklist_lines=checklist_lines,
            file_lines=file_lines,
            history_lines=history_lines,
            user_message=user_message,
        )
        return await self.ai_client.generate_text(
            build_messages(system_prompt=CHAT_SYSTEM_PROMPT_WITH_TOOLS, user_prompt=prompt),
            temperature=0.2,
            max_tokens=900,
        )

    async def stream_answer(
        self,
        *,
        analysis_summary: str,
        checklist_lines: list[str],
        file_lines: list[str],
        history_lines: list[str],
        user_message: str,
    ) -> AsyncIterator[str]:
        prompt = build_chat_context(
            analysis_summary=analysis_summary,
            checklist_lines=checklist_lines,
            file_lines=file_lines,
            history_lines=history_lines,
            user_message=user_message,
        )
        async for chunk in self.ai_client.stream_text(
            build_messages(system_prompt=CHAT_SYSTEM_PROMPT_WITH_TOOLS, user_prompt=prompt),
            temperature=0.2,
            max_tokens=900,
        ):
            yield chunk

    async def stream_answer_with_tools(
        self,
        *,
        analysis_summary: str,
        checklist_lines: list[str],
        file_lines: list[str],
        history_lines: list[str],
        user_message: str,
        tool_context: ToolContext,
    ) -> AsyncIterator[str]:
        """Stream answer with tool-use loop. Yields only text chunks to the caller."""
        prompt = build_chat_context(
            analysis_summary=analysis_summary,
            checklist_lines=checklist_lines,
            file_lines=file_lines,
            history_lines=history_lines,
            user_message=user_message,
        )
        messages = build_messages(system_prompt=CHAT_SYSTEM_PROMPT_WITH_TOOLS, user_prompt=prompt)

        for round_idx in range(_MAX_TOOL_ROUNDS):
            collected_text: list[str] = []
            tool_call_event: ToolCallEvent | None = None

            async for event in self.ai_client.stream_text_with_tools(
                messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.2,
                max_tokens=1500,
            ):
                if isinstance(event, TextChunkEvent):
                    collected_text.append(event.text)
                    yield event.text
                elif isinstance(event, ToolCallEvent):
                    tool_call_event = event
                elif isinstance(event, DoneEvent):
                    pass

            if tool_call_event is None or not tool_call_event.tool_calls:
                break

            # Build assistant message with tool calls
            assistant_text = "".join(collected_text)
            messages.append(AIMessage(
                role="assistant",
                content=assistant_text,
                tool_calls=tool_call_event.tool_calls,
            ))

            # Execute each tool and append results
            for tc in tool_call_event.tool_calls:
                logger.info("Executing tool %s (round %d): %s", tc.name, round_idx + 1, tc.arguments)
                result = await execute_tool(tc.name, tc.arguments, tool_context)
                messages.append(AIMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                ))
