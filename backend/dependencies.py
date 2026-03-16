"""Dependency definitions for FastAPI routes."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, settings
from backend.db.connection import get_session_factory
from backend.services.mail import MailService, build_mail_service

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


# async def get_github_client() -> AsyncIterator[GitHubClient]:
#     """Yield a configured GitHub API client.

#     Yields:
#         GitHubClient: A GitHub API client instance.
#     """

#     async with GitHubClient(base_url=settings.GITHUB_API_BASE_URL) as client:
#         yield client


async def get_ai_provider_client() -> AsyncIterator[Any]:
    """Yield the configured AI provider client.

    Yields:
        object: A provider-specific client instance.

    Raises:
        RuntimeError: If the selected provider is missing configuration.
        ValueError: If the configured provider is unsupported.
    """

    provider = settings.AI_PROVIDER.lower()
    client: Any

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required when AI_PROVIDER is set to 'anthropic'.")

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER is set to 'openai'.")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    elif provider == "ollama":
        client = httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=60.0)
    else:
        raise ValueError(f"Unsupported AI provider: {settings.AI_PROVIDER}")

    logger.debug("Initialized AI provider client", extra={"provider": provider})

    try:
        yield client
    finally:
        aclose = getattr(client, "aclose", None)
        if callable(aclose):
            await aclose()
