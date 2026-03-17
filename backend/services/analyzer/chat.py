"""Chat context builder powered by the unified AI provider."""

from __future__ import annotations

from backend.services.ai import AIProviderClient
from backend.services.analyzer.helpers import build_messages
from backend.services.analyzer.prompts import CHAT_SYSTEM_PROMPT, build_chat_context


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
            build_messages(system_prompt=CHAT_SYSTEM_PROMPT, user_prompt=prompt),
            temperature=0.2,
            max_tokens=900,
        )
