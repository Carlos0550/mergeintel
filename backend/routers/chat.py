"""Routes for contextual PR chat endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.chat import ChatController
from backend.dependencies import get_ai_provider_client, get_current_user, get_db_session
from backend.schemas.base import ErrorResponse
from backend.schemas.chat import ChatRequest
from backend.schemas.user_managment import CurrentUser
from backend.services.ai import AIProviderClient


router = APIRouter(prefix="/chat", tags=["contextual pr chat"])


@router.post("/{analysis_id}/message", response_model=None)
async def send_chat_message(
    analysis_id: UUID,
    data: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
):
    controller = ChatController(db=db, ai_client=ai_client, current_user_id=UUID(current_user.id))
    result = await controller.send_message(analysis_id, data.message)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


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
