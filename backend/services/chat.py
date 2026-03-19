"""Application service for contextual PR chat sessions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.chat import ChatMessage, ChatRole, ChatSession
from backend.models.pr_analysis import PRAnalysis
from backend.services.ai import AIProviderClient
from backend.services.ai.tools import ToolContext
from backend.services.analyzer import AnalysisChatService
from backend.services.github.client import GitHubClient


class ChatService:
    """Persist chat messages and delegate answer generation to the analyzer chat service."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        ai_client: AIProviderClient,
        current_user_id: UUID,
        github_client: GitHubClient | None = None,
    ) -> None:
        self.session = session
        self.ai_client = ai_client
        self.current_user_id = current_user_id
        self.github_client = github_client

    async def send_message(self, analysis_id: UUID, user_message: str) -> ChatSession:
        analysis = await self._get_analysis(analysis_id)
        chat_session = await self._get_or_create_chat_session(analysis_id)
        chat_context = self._build_chat_context(
            analysis=analysis,
            chat_session=chat_session,
            user_message=user_message,
        )
        await self._persist_user_message(chat_session.id, user_message)

        answer = await AnalysisChatService(self.ai_client).answer(
            **chat_context
        )
        await self._persist_assistant_message(chat_session.id, answer)
        return await self.get_history(analysis_id)

    async def stream_message(self, analysis_id: UUID, user_message: str) -> AsyncIterator[dict[str, Any]]:
        analysis = await self._get_analysis(analysis_id)
        chat_session = await self._get_or_create_chat_session(analysis_id)
        chat_context = self._build_chat_context(
            analysis=analysis,
            chat_session=chat_session,
            user_message=user_message,
        )
        await self._persist_user_message(chat_session.id, user_message)

        tool_context = ToolContext(analysis=analysis, github_client=self.github_client)
        chat_service = AnalysisChatService(self.ai_client)

        chunks: list[str] = []
        try:
            async for chunk in chat_service.stream_answer_with_tools(
                **chat_context, tool_context=tool_context,
            ):
                chunks.append(chunk)
                yield {"event": "chunk", "data": {"content": chunk}}
        except Exception:
            await self.session.rollback()
            raise

        answer = "".join(chunks).strip()
        assistant_record = await self._persist_assistant_message(chat_session.id, answer)
        yield {
            "event": "done",
            "data": {
                "session_id": str(chat_session.id),
                "analysis_id": str(chat_session.analysis_id),
                "message": self._message_to_payload(assistant_record),
            },
        }

    async def get_history(self, analysis_id: UUID) -> ChatSession:
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.analysis_id == analysis_id, ChatSession.user_id == self.current_user_id)
            .options(selectinload(ChatSession.messages))
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is None:
            chat_session = await self._get_or_create_chat_session(analysis_id)
            await self.session.commit()
            await self.session.refresh(chat_session, attribute_names=["messages"])
        return chat_session

    async def clear_history(self, analysis_id: UUID) -> None:
        chat_session = await self.get_history(analysis_id)
        await self.session.execute(delete(ChatMessage).where(ChatMessage.session_id == chat_session.id))
        await self.session.commit()

    async def _get_analysis(self, analysis_id: UUID) -> PRAnalysis:
        result = await self.session.execute(
            select(PRAnalysis)
            .where(PRAnalysis.id == analysis_id, PRAnalysis.user_id == self.current_user_id)
            .options(
                selectinload(PRAnalysis.checklist_items),
                selectinload(PRAnalysis.files),
                selectinload(PRAnalysis.authors),
                selectinload(PRAnalysis.commits),
            )
        )
        return result.scalar_one()

    async def _get_or_create_chat_session(self, analysis_id: UUID) -> ChatSession:
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.analysis_id == analysis_id, ChatSession.user_id == self.current_user_id)
            .options(selectinload(ChatSession.messages))
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is not None:
            return chat_session

        chat_session = ChatSession(analysis_id=analysis_id, user_id=self.current_user_id)
        self.session.add(chat_session)
        await self.session.flush()
        return chat_session

    async def _persist_user_message(self, session_id: UUID, user_message: str) -> ChatMessage:
        user_record = ChatMessage(session_id=session_id, role=ChatRole.USER, content=user_message)
        self.session.add(user_record)
        await self.session.commit()
        await self.session.refresh(user_record)
        return user_record

    async def _persist_assistant_message(self, session_id: UUID, answer: str) -> ChatMessage:
        assistant_record = ChatMessage(session_id=session_id, role=ChatRole.ASSISTANT, content=answer)
        self.session.add(assistant_record)
        await self.session.commit()
        await self.session.refresh(assistant_record)
        return assistant_record

    @staticmethod
    def _build_chat_context(
        *,
        analysis: PRAnalysis,
        chat_session: ChatSession,
        user_message: str,
    ) -> dict[str, Any]:
        role_labels = {
            ChatRole.USER: "usuario",
            ChatRole.ASSISTANT: "asistente",
            ChatRole.SYSTEM: "sistema",
        }
        history_lines = [
            f"{role_labels.get(item.role, item.role.value)}: {item.content}"
            for item in chat_session.messages
        ] + [f"usuario: {user_message}"]
        checklist_lines = [f"- [{item.severity.value}] {item.title}: {item.details or ''}".strip() for item in analysis.checklist_items]
        file_lines = [f"- {item.path} ({item.change_type}, +{item.additions}/-{item.deletions})" for item in analysis.files]
        return {
            "analysis_summary": analysis.summary_text or "",
            "checklist_lines": checklist_lines,
            "file_lines": file_lines,
            "history_lines": history_lines,
            "user_message": user_message,
        }

    @staticmethod
    def _message_to_payload(item: ChatMessage) -> dict[str, str]:
        return {
            "id": str(item.id),
            "role": item.role.value,
            "content": item.content,
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def to_response_payload(chat_session: ChatSession) -> dict:
        sorted_messages = sorted(chat_session.messages, key=lambda item: item.created_at)
        return {
            "session_id": str(chat_session.id),
            "analysis_id": str(chat_session.analysis_id),
            "history": [
                ChatService._message_to_payload(item) for item in sorted_messages
            ],
        }
