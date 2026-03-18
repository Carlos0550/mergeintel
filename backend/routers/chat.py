"""Routes for contextual PR chat endpoints."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.chat import ChatController
from backend.exceptions import AppError
from backend.dependencies import get_ai_provider_client, get_current_user, get_db_session, get_github_client
from backend.schemas.base import ErrorResponse
from backend.schemas.chat import ChatRequest
from backend.schemas.user_managment import CurrentUser
from backend.services.ai import AIProviderClient
from backend.services.chat import ChatService
from backend.services.github.client import GitHubClient


router = APIRouter(prefix="/chat", tags=["contextual pr chat"])


def _sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{analysis_id}/message", response_model=None)
async def send_chat_message(
    analysis_id: UUID,
    data: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
    github_client: GitHubClient = Depends(get_github_client),
):
    controller = ChatController(
        db=db, ai_client=ai_client, current_user_id=UUID(current_user.id), github_client=github_client,
    )
    result = await controller.send_message(analysis_id, data.message)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.post("/{analysis_id}/stream", response_model=None)
async def stream_chat_message(
    analysis_id: UUID,
    data: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
    github_client: GitHubClient = Depends(get_github_client),
):
    service = ChatService(
        session=db, ai_client=ai_client, current_user_id=UUID(current_user.id), github_client=github_client,
    )

    async def event_stream():
        try:
            async for event in service.stream_message(analysis_id, data.message):
                yield _sse_event(event["event"], event["data"])
        except AppError as exc:
            yield _sse_event(
                "error",
                {
                    "message": exc.message,
                    "code": exc.err_code,
                    "status_code": exc.status_code,
                },
            )
        except Exception as exc:
            yield _sse_event(
                "error",
                {
                    "message": "No se pudo responder el chat.",
                    "code": "CHAT_STREAM_ERROR",
                    "detail": str(exc),
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{analysis_id}/history", response_model=None)
async def get_chat_history(
    analysis_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
):
    controller = ChatController(db=db, ai_client=ai_client, current_user_id=UUID(current_user.id))
    result = await controller.get_history(analysis_id)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.delete("/{analysis_id}", response_model=None)
async def clear_chat_history(
    analysis_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
):
    controller = ChatController(db=db, ai_client=ai_client, current_user_id=UUID(current_user.id))
    result = await controller.clear_history(analysis_id)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result
