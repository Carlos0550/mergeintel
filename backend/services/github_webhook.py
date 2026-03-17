"""Webhook helpers for GitHub pull request events."""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.exceptions import AppError
from backend.models.pr_analysis import PRAnalysis
from backend.models.user import OAuthAccount, OauthProviders


SUPPORTED_PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize"}


def verify_github_webhook_signature(*, raw_body: bytes, signature: str | None) -> None:
    """Validate the GitHub webhook signature using the configured shared secret."""

    secret = (settings.GITHUB_WEBHOOK_SECRET or "").strip()
    if not secret:
        raise AppError(
            "GITHUB_WEBHOOK_SECRET no esta configurado.",
            err_code="GITHUB_WEBHOOK_NOT_CONFIGURED",
            status_code=500,
        )
    if not signature:
        raise AppError(
            "Falta la firma del webhook.",
            err_code="GITHUB_WEBHOOK_SIGNATURE_MISSING",
            status_code=401,
        )

    expected_signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise AppError(
            "La firma del webhook no es valida.",
            err_code="GITHUB_WEBHOOK_SIGNATURE_INVALID",
            status_code=401,
        )


async def resolve_webhook_user_id(session: AsyncSession, *, owner: str, repo: str, sender_login: str | None) -> UUID | None:
    """Resolve which MergeIntel user should own a webhook-triggered analysis."""

    result = await session.execute(
        select(PRAnalysis.user_id)
        .where(PRAnalysis.repo_full_name == f"{owner}/{repo}")
        .order_by(PRAnalysis.updated_at.desc())
    )
    existing_user_id = result.scalar_one_or_none()
    if existing_user_id:
        return existing_user_id

    logins = [owner]
    if sender_login:
        logins.append(sender_login)

    result = await session.execute(
        select(OAuthAccount.user_id).where(
            OAuthAccount.provider == OauthProviders.GITHUB,
            OAuthAccount.provider_login.in_(logins),
        )
    )
    return result.scalar_one_or_none()
