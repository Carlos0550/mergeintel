"""Chat context builder powered by the unified AI provider."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator

from backend.services.ai import AIProviderClient
from backend.services.ai.base import AIMessage, DoneEvent, TextChunkEvent, ToolCallEvent
from backend.services.ai.tools import TOOL_DEFINITIONS, ToolContext, execute_tool
from backend.services.analyzer.helpers import build_messages
from backend.services.analyzer.prompts import (
    CHAT_SYSTEM_PROMPT_FUNCTION_CALLING,
    CHAT_SYSTEM_PROMPT_WITH_TOOLS,
    build_chat_context,
)

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 5


_MALFORMED_TOOL_RE = re.compile(r"'(\w+)\s+(\{.*?\})'", re.DOTALL)


async def _try_recover_malformed_tool_call(error_msg: str, ctx: ToolContext) -> str | None:
    """Try to extract tool name and args from a malformed tool call error and execute it."""
    match = _MALFORMED_TOOL_RE.search(error_msg)
    if not match:
        return None
    tool_name = match.group(1)
    try:
        args = json.loads(match.group(2))
    except json.JSONDecodeError:
        return None
    logger.info("Recovered malformed tool call: %s(%s)", tool_name, args)
    return await execute_tool(tool_name, args, ctx)


def _strip_tool_messages(messages: list[AIMessage]) -> list[AIMessage]:
    """Collapse tool call/result messages into a single assistant context message.

    When falling back from tool-use to text-only mode, the message history may
    contain assistant messages with ``tool_calls`` and ``tool`` role messages that
    are invalid for a plain chat completion request.  This helper keeps system and
    user messages intact and merges the tool interaction into a single assistant
    message summarising the data that was retrieved.
    """
    clean: list[AIMessage] = []
    tool_results: list[str] = []
    for m in messages:
        if m.role == "tool":
            tool_results.append(m.content)
        elif m.role == "assistant" and m.tool_calls:
            # Skip the raw tool-call assistant message; we'll inject results below.
            continue
        else:
            clean.append(m)
    if tool_results:
        summary = "\n\n".join(tool_results)
        clean.append(AIMessage(
            role="assistant",
            content=f"[Datos obtenidos de herramientas previas]\n{summary}\n\nAhora respondo basándome en estos datos:",
        ))
    return clean


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
        # Use the function-calling prompt (no text tool descriptions) to avoid
        # confusing models that mix up text descriptions with structured API calls.
        messages = build_messages(system_prompt=CHAT_SYSTEM_PROMPT_FUNCTION_CALLING, user_prompt=prompt)

        for round_idx in range(_MAX_TOOL_ROUNDS):
            collected_text: list[str] = []
            tool_call_event: ToolCallEvent | None = None

            try:
                async for event in self.ai_client.stream_text_with_tools(
                    messages,
                    tools=TOOL_DEFINITIONS,
                    temperature=0.2,
                    max_tokens=1500,
                ):
                    if isinstance(event, TextChunkEvent):
                        collected_text.append(event.text)
                    elif isinstance(event, ToolCallEvent):
                        if tool_call_event is None:
                            tool_call_event = event
                        else:
                            tool_call_event.tool_calls.extend(event.tool_calls)
                    elif isinstance(event, DoneEvent):
                        pass
            except Exception as exc:
                # Groq sometimes generates malformed tool calls where the model puts
                # the arguments inside the tool name (e.g. 'get_file_diff {"file_path": "..."}').
                # Try to parse the malformed name, execute the tool, and continue with
                # a text-only fallback that includes the tool result.
                err_str = str(exc)
                if "tool call validation" in err_str.lower() or "not in request.tools" in err_str.lower():
                    logger.warning("Tool call validation failed (round %d), attempting recovery: %s", round_idx + 1, exc)
                    tool_result = await _try_recover_malformed_tool_call(err_str, tool_context)
                    fallback_messages = _strip_tool_messages(messages)
                    if tool_result is not None:
                        fallback_messages.append(AIMessage(
                            role="assistant",
                            content=f"[Datos obtenidos]\n{tool_result}\n\nAhora respondo basándome en estos datos:",
                        ))
                    async for chunk in self.ai_client.stream_text(
                        fallback_messages,
                        temperature=0.2,
                        max_tokens=1500,
                    ):
                        yield chunk
                    return
                raise

            if tool_call_event is None or not tool_call_event.tool_calls:
                for chunk in collected_text:
                    yield chunk
                break

            # Providers like Groq are stricter here: when the assistant emits tool calls,
            # replay only the tool call metadata and discard any partial preamble text.
            messages.append(AIMessage(
                role="assistant",
                content="",
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
