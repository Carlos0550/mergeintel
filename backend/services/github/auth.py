"""Shared helpers for GitHub-authenticated user flows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.exceptions import AppError
from backend.models.user import OAuthAccount, OauthProviders
from backend.utils.security import decrypt_secret


async def get_github_access_token_for_user(session: AsyncSession, user_id: UUID) -> str:
    """Return the decrypted GitHub token for a linked user."""

    result = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.provider == OauthProviders.GITHUB,
            OAuthAccount.is_active.is_(True),
        )
    )
    oauth_account = result.scalar_one_or_none()
    if oauth_account is None or not oauth_account.access_token:
        raise AppError(
            "Debes enlazar una cuenta de GitHub antes de continuar.",
            err_code="GITHUB_ACCOUNT_REQUIRED",
            status_code=403,
        )

    return decrypt_secret(oauth_account.access_token, settings.GITHUB_TOKEN_ENCRYPTION_KEY or "")
