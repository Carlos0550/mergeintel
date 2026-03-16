"""User authentication and management service using SQLAlchemy ORM."""

from __future__ import annotations

import logging

from backend.models.user import User, UserRole, UserStatus
from backend.schemas.user_managment import CreateUserRequest, CurrentUser
from backend.utils.security import hash_string
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class UserService:

    def __init__(
        self,
        session: AsyncSession,
        *,
        current_user: CurrentUser | None = None,
    ) -> None:
        self.session = session
        self.current_user = current_user

    async def create_user(self, data: CreateUserRequest) -> User:
        user = User(
            name=data.name,
            email=data.email,
            password=hash_string(data.password),
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        self.session.add(user)
        try:
            await self.session.commit()
            await self.session.refresh(user)
            logger.info(
                "User created successfully",
                extra={
                    "user_id": str(user.id),
                    "user_role": user.role.value,
                    "user_status": user.status.value,
                },
            )
            return user
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                "Failed to create user",
                extra={
                    "operation": "create_user",
                    "request_user_email": data.email,
                },
            )
            raise

    async def get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email. Read-only; no commit needed."""
        result = await self.session.execute(select(User).where(User.email == email))
        return await result.scalar_one_or_none()
