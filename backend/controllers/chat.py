"""Controllers for contextual PR chat routes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.decorators import handle_controller_errors
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.services.ai import AIProviderClient
from backend.services.chat import ChatService


class ChatController:
    """Controller for persisted PR chat flows."""

    def __init__(self, *, db: AsyncSession, ai_client: AIProviderClient, current_user_id: UUID) -> None:
        self.chat_service = ChatService(session=db, ai_client=ai_client, current_user_id=current_user_id)

    @handle_controller_errors(default_message="No se pudo responder el chat.", default_code="CHAT_SEND_ERROR")
    async def send_message(self, analysis_id: UUID, message: str) -> SucessWithData | ErrorResponse:
        chat_session = await self.chat_service.send_message(analysis_id, message)
        payload = self.chat_service.to_response_payload(chat_session)
        assistant_message = payload["history"][-1]["content"] if payload["history"] else ""
        return SucessWithData(
            success=True,
            message="Chat response generated successfully.",
            result={
                "session_id": payload["session_id"],
                "analysis_id": payload["analysis_id"],
                "answer": assistant_message,
                "history": payload["history"],
            },
        )

    @handle_controller_errors(default_message="No se pudo recuperar el historial del chat.", default_code="CHAT_HISTORY_ERROR")
    async def get_history(self, analysis_id: UUID) -> SucessWithData | ErrorResponse:
        chat_session = await self.chat_service.get_history(analysis_id)
        payload = self.chat_service.to_response_payload(chat_session)
        return SucessWithData(success=True, message="Chat history retrieved successfully.", result=payload)

    @handle_controller_errors(default_message="No se pudo limpiar el historial.", default_code="CHAT_CLEAR_ERROR")
    async def clear_history(self, analysis_id: UUID) -> SucessWithData | ErrorResponse:
        await self.chat_service.clear_history(analysis_id)
        return SucessWithData(success=True, message="Chat history cleared successfully.", result={"cleared": True})
