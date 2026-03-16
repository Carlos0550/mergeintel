"""Async SQLAlchemy database connection management."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_database_url() -> str:
    """Return the SQLAlchemy async database URL.

    Returns:
        str: Database URL using the asyncpg SQLAlchemy dialect.
    """

    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


async def create_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache the global async SQLAlchemy session factory.

    Returns:
        async_sessionmaker[AsyncSession]: The configured async session factory.
    """

    global engine
    global session_factory

    if session_factory is not None:
        return session_factory

    logger.info(
        "Creating SQLAlchemy async engine",
        extra={"database_backend": get_async_database_url().split("://", maxsplit=1)[0]},
    )
    engine = create_async_engine(
        get_async_database_url(),
        future=True,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return session_factory


async def close_engine() -> None:
    """Dispose the global async SQLAlchemy engine."""

    global engine
    global session_factory

    if engine is None:
        return

    logger.info(
        "Disposing SQLAlchemy async engine",
        extra={"database_backend": get_async_database_url().split("://", maxsplit=1)[0]},
    )
    await engine.dispose()
    engine = None
    session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active async SQLAlchemy session factory.

    Returns:
        async_sessionmaker[AsyncSession]: The configured session factory.

    Raises:
        RuntimeError: If the session factory has not been initialized.
    """

    if session_factory is None:
        raise RuntimeError("Database session factory has not been initialized.")

    return session_factory
