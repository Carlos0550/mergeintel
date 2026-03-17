"""Dependency definitions for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging
from uuid import UUID

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, settings
from backend.db.connection import get_session_factory
from backend.exceptions import AppError
from backend.models.session import UserSession
from backend.models.user import OAuthAccount, OauthProviders, User
from backend.schemas.user_managment import CurrentUser
from backend.services.ai import AIProviderClient, build_ai_provider_client
from backend.services.github import GitHubClient
from backend.services.mail import MailService, build_mail_service
from backend.timezone import now_in_app_timezone
from backend.utils.security import decrypt_secret, hash_token

logger = logging.getLogger(__name__)


async def get_settings() -> Settings:
    """Return the application settings instance.

    Returns:
        Settings: The loaded application settings.
    """

    return settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy database session.

    Yields:
        AsyncSession: The active SQLAlchemy async session.
    """

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def get_mail_service() -> MailService:
    """Return the configured mail service for the current environment."""

    return build_mail_service(settings)


async def get_ai_provider_client() -> AsyncIterator[AIProviderClient]:
    """Yield the configured AI provider client.

    Yields:
        AIProviderClient: A provider-agnostic AI client implementation.
    """

    client = build_ai_provider_client(settings)

    logger.debug("Initialized AI provider client", extra={"provider": settings.AI_PROVIDER.lower()})

    try:
        yield client
    finally:
        await client.aclose()


async def get_current_user(
    session_token: str | None = Cookie(default=None, alias="mergeintel_session"),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Resolve the current authenticated user from the session cookie."""

    current_user = await _resolve_current_user(session_token=session_token, db=db)
    if current_user is None:
        raise AppError(
            "Debes iniciar sesion para acceder a este recurso.",
            err_code="AUTH_REQUIRED",
            status_code=401,
        )
    return current_user


async def get_optional_current_user(
    session_token: str | None = Cookie(default=None, alias="mergeintel_session"),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser | None:
    """Resolve the current user if a valid session cookie is present."""

    return await _resolve_current_user(session_token=session_token, db=db)


async def _resolve_current_user(
    *,
    session_token: str | None,
    db: AsyncSession,
) -> CurrentUser | None:
    if not session_token:
        return None

    token_hash = hash_token(session_token)
    result = await db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == token_hash,
            UserSession.is_active.is_(True),
            User.is_active.is_(True),
        )
    )
    row = result.first()
    if row is None:
        return None
    _, user = row
    user_session = row[0]
    if user_session.expires_at <= now_in_app_timezone():
        user_session.is_active = False
        await db.commit()
        return None
    return CurrentUser(
        id=str(user.id),
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
    )


async def get_github_client(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AsyncIterator[GitHubClient]:
    """Yield a GitHub API client for the current authenticated user."""

    result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == UUID(current_user.id),
            OAuthAccount.provider == OauthProviders.GITHUB,
            OAuthAccount.is_active.is_(True),
        )
    )
    oauth_account = result.scalar_one_or_none()
    if oauth_account is None or not oauth_account.access_token:
        raise AppError(
            "Debes enlazar una cuenta de GitHub antes de analizar un PR.",
            err_code="GITHUB_ACCOUNT_REQUIRED",
            status_code=403,
        )

    access_token = decrypt_secret(oauth_account.access_token, settings.GITHUB_TOKEN_ENCRYPTION_KEY or "")
    async with GitHubClient(access_token=access_token, base_url=settings.GITHUB_API_BASE_URL) as client:
        yield client
