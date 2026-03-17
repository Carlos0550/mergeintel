"""Controllers for GitHub webhook handling."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.decorators import handle_controller_errors
from backend.config import settings
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.pr import AnalyzePRRequest
from backend.services.ai import AIProviderClient
from backend.services.github import GitHubClient
from backend.services.github_webhook import resolve_webhook_user_id, verify_github_webhook_signature
from backend.services.pr import PRService


class GitHubWebhookController:
    """Controller for validated GitHub webhook events."""

    def __init__(self, *, db: AsyncSession, ai_client: AIProviderClient) -> None:
        self.db = db
        self.ai_client = ai_client

    @handle_controller_errors(default_message="No se pudo procesar el webhook.", default_code="GITHUB_WEBHOOK_ERROR")
    async def handle_pull_request_event(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        payload: dict,
    ) -> SucessWithData | ErrorResponse:
        verify_github_webhook_signature(raw_body=raw_body, signature=signature)
        action = str(payload.get("action") or "").strip()
        if action not in {"opened", "reopened", "synchronize"}:
            return SucessWithData(
                success=True,
                message="Webhook action ignored.",
                result={"processed": False, "action": action},
            )

        repository = payload.get("repository") or {}
        pull_request = payload.get("pull_request") or {}
        owner = str(((repository.get("owner") or {}).get("login")) or "").strip()
        repo = str(repository.get("name") or "").strip()
        pr_number = int(payload.get("number") or 0)
        sender_login = str(((payload.get("sender") or {}).get("login")) or "").strip() or None

        user_id = await resolve_webhook_user_id(self.db, owner=owner, repo=repo, sender_login=sender_login)
        if user_id is None:
            return SucessWithData(
                success=True,
                message="Webhook received but no MergeIntel user could be resolved.",
                result={"processed": False, "reason": "owner_not_resolved"},
            )

        from backend.services.github.auth import get_github_access_token_for_user

        github_token = await get_github_access_token_for_user(self.db, user_id)
        async with GitHubClient(access_token=github_token, base_url=settings.GITHUB_API_BASE_URL) as github_client:
            pr_service = PRService(
                session=self.db,
                github_client=github_client,
                ai_client=self.ai_client,
                current_user_id=UUID(str(user_id)),
            )
            analysis = await pr_service.analyze_pull_request(
                AnalyzePRRequest(
                    pr_url=str(pull_request.get("html_url") or ""),
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    author_scopes={},
                )
            )

        return SucessWithData(
            success=True,
            message="Webhook processed successfully.",
            result={"processed": True, "analysis_id": str(analysis.id), "action": action},
        )
