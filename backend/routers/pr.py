"""Routes for pull request analysis endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.pr import PRController
from backend.dependencies import get_ai_provider_client, get_current_user, get_db_session, get_github_client
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.pr import AnalyzePRRequest
from backend.schemas.user_managment import CurrentUser
from backend.services.ai import AIProviderClient
from backend.services.github import GitHubClient


router = APIRouter(prefix="/pr", tags=["pull request analysis"])


@router.post(
    "/analyze",
    response_model=None,
    responses={200: {"model": SucessWithData}, 400: {"model": ErrorResponse}},
)
async def analyze_pull_request(
    data: AnalyzePRRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    github_client: GitHubClient = Depends(get_github_client),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
):
    controller = PRController(
        db=db,
        github_client=github_client,
        ai_client=ai_client,
        current_user_id=UUID(current_user.id),
    )
    result = await controller.analyze(data)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.get("/history", response_model=None)
async def list_history(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    controller = PRController(db=db, github_client=None, ai_client=None, current_user_id=UUID(current_user.id))
    result = await controller.list_history()
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.get("/{analysis_id}", response_model=None)
async def get_analysis(
    analysis_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    controller = PRController(db=db, github_client=None, ai_client=None, current_user_id=UUID(current_user.id))
    result = await controller.get_analysis(analysis_id)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.get("/{analysis_id}/checklist", response_model=None)
async def get_checklist(
    analysis_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    controller = PRController(db=db, github_client=None, ai_client=None, current_user_id=UUID(current_user.id))
    result = await controller.get_checklist(analysis_id)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.delete("/{analysis_id}", response_model=None)
async def delete_analysis(
    analysis_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    controller = PRController(db=db, github_client=None, ai_client=None, current_user_id=UUID(current_user.id))
    result = await controller.delete_analysis(analysis_id)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result
