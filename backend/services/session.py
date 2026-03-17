"""Persistent session management for authenticated users."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.exceptions import AppError
from backend.models.session import UserSession
from backend.models.user import User
from backend.timezone import now_in_app_timezone
from backend.utils.security import generate_opaque_token, hash_token


SESSION_TTL_DAYS = 30


class SessionService:
    """Create and revoke persisted server-side sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, user: User) -> tuple[UserSession, str]:
        token = generate_opaque_token()
        current_time = now_in_app_timezone()
        user_session = UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=current_time + timedelta(days=SESSION_TTL_DAYS),
            last_seen_at=current_time,
        )
        self.session.add(user_session)
        await self.session.commit()
        return user_session, token

    async def revoke_session(self, session_token: str) -> None:
        result = await self.session.execute(
            select(UserSession).where(
                UserSession.token_hash == hash_token(session_token),
                UserSession.is_active.is_(True),
            )
        )
        user_session = result.scalar_one_or_none()
        if user_session is None:
            raise AppError(
                "La sesion no es valida o ya fue cerrada.",
                err_code="INVALID_SESSION",
                status_code=401,
            )

        user_session.is_active = False
        await self.session.commit()

    async def revoke_user_sessions(self, user_id: UUID) -> None:
        result = await self.session.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.is_active.is_(True),
            )
        )
        sessions = result.scalars().all()
        for item in sessions:
            item.is_active = False
        await self.session.commit()
