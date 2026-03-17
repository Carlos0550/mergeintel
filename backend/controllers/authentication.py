"""Authentication controllers."""

from __future__ import annotations

import logging
from typing import Union
from uuid import UUID

from backend.services.mail import MailService
from backend.services.authentication import UserService
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest, GitHubOAuthRequest
from backend.controllers.decorators import handle_controller_errors
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UserController:
    """Controller for user-related authentication flows."""

    def __init__(self, db: AsyncSession, mail_service: MailService) -> None:
        self.user_service = UserService(session=db, mail_service=mail_service)

    @handle_controller_errors(
        default_message="No se pudo crear el usuario.",
        default_code="CREATE_USER_ERROR",
    )
    async def create_user(self, data: CreateUserRequest) -> Union[SucessWithData, ErrorResponse]:
        user = await self.user_service.create_user(data)
        return SucessWithData(
            success=True,
            message="User created successfully.",
            result={
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "status": user.status.value,
            },
        )

    @handle_controller_errors(
        default_message="No se pudo crear el usuario con GitHub.",
        default_code="CREATE_GITHUB_USER_ERROR",
    )
    async def create_user_with_github(self, data: GitHubOAuthRequest) -> Union[SucessWithData, ErrorResponse]:
        user, oauth_account = await self.user_service.create_user_with_github(data)
        return SucessWithData(
            success=True,
            message="GitHub account processed successfully.",
            result={
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "status": user.status.value,
                "github": {
                    "provider": oauth_account.provider.value,
                    "provider_user_id": oauth_account.provider_user_id,
                    "provider_login": oauth_account.provider_login,
                },
            },
        )

    @handle_controller_errors(
        default_message="No se pudo enlazar la cuenta de GitHub.",
        default_code="LINK_GITHUB_ACCOUNT_ERROR",
    )
    async def link_github_account(
        self,
        user_id: UUID,
        data: GitHubOAuthRequest,
    ) -> Union[SucessWithData, ErrorResponse]:
        user, oauth_account = await self.user_service.link_github_account(user_id, data)
        return SucessWithData(
            success=True,
            message="GitHub account linked successfully.",
            result={
                "id": str(user.id),
                "email": user.email,
                "github": {
                    "provider": oauth_account.provider.value,
                    "provider_user_id": oauth_account.provider_user_id,
                    "provider_login": oauth_account.provider_login,
                },
            },
        )
