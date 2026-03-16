"""User authentication and management service using SQLAlchemy ORM."""

from __future__ import annotations

import logging

from backend.models.user import User, UserRole, UserStatus
from backend.services.mail import EmailPayload, MailService, render_html_template
from backend.schemas.user_managment import CreateUserRequest, CurrentUser
from backend.utils.security import hash_string
from backend.utils.text import capitalize_words
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class UserService:

    def __init__(
        self,
        session: AsyncSession,
        mail_service: MailService,
        *,
        current_user: CurrentUser | None = None,
    ) -> None:
        self.session = session
        self.mail_service = mail_service
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
            html_content = render_html_template(
                "backend/templates/welcome.html",
                user_name=capitalize_words(user.name),
                user_email=user.email,
            )
            await self.mail_service.send_email(
                EmailPayload(
                    to=[user.email],
                    subject="Welcome to MergeIntel",
                    html=html_content,
                )
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
