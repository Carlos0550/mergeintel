"""Routes for GitHub webhook events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.github import GitHubWebhookController
from backend.dependencies import get_ai_provider_client, get_db_session
from backend.schemas.base import ErrorResponse
from backend.services.ai import AIProviderClient


router = APIRouter(prefix="/github", tags=["github integration"])


@router.post("/webhook", response_model=None)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
    ai_client: AIProviderClient = Depends(get_ai_provider_client),
):
    raw_body = await request.body()
    payload = await request.json()
    controller = GitHubWebhookController(db=db, ai_client=ai_client)
    result = await controller.handle_pull_request_event(
        raw_body=raw_body,
        signature=x_hub_signature_256,
        payload=payload,
    )
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result
