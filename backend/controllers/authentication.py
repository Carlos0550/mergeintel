"""Authentication controllers."""

from __future__ import annotations

import logging
from typing import Union
from uuid import UUID

from backend.exceptions import AppError
from backend.services.mail import MailService
from backend.services.authentication import UserService
from backend.services.session import SessionService
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest, CurrentUser, GitHubOAuthRequest, LoginRequest
from backend.controllers.decorators import handle_controller_errors
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UserController:
    """Controller for user-related authentication flows."""

    def __init__(self, db: AsyncSession, mail_service: MailService) -> None:
        self.user_service = UserService(session=db, mail_service=mail_service)
        self.session_service = SessionService(session=db)

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
        default_message="No se pudo iniciar sesion.",
        default_code="LOGIN_ERROR",
    )
    async def login(self, data: LoginRequest) -> tuple[SucessWithData, str]:
        user = await self.user_service.authenticate_user(data)
        _, session_token = await self.session_service.create_session(user)
        return (
            SucessWithData(
                success=True,
                message="Login successful.",
                result={
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "role": user.role.value,
                    "status": user.status.value,
                },
            ),
            session_token,
        )

    @handle_controller_errors(
        default_message="No se pudo obtener el usuario actual.",
        default_code="CURRENT_USER_ERROR",
    )
    async def get_current_user_data(self, current_user: CurrentUser) -> Union[SucessWithData, ErrorResponse]:
        return SucessWithData(
            success=True,
            message="Current user resolved successfully.",
            result=current_user.model_dump(mode="json"),
        )

    @handle_controller_errors(
        default_message="No se pudo cerrar la sesion.",
        default_code="LOGOUT_ERROR",
    )
    async def logout(self, session_token: str) -> Union[SucessWithData, ErrorResponse]:
        await self.session_service.revoke_session(session_token)
        return SucessWithData(
            success=True,
            message="Logout successful.",
            result={"revoked": True},
        )

    @handle_controller_errors(
        default_message="No se pudo crear la sesion.",
        default_code="SESSION_CREATE_ERROR",
    )
    async def create_session_for_user(self, user_id: UUID) -> tuple[SucessWithData, str]:
        user = await self.user_service.get_user_by_id(user_id)
        if user is None:
            raise AppError(
                "El usuario no existe.",
                err_code="USER_NOT_FOUND",
                status_code=404,
            )

        _, session_token = await self.session_service.create_session(user)
        return (
            SucessWithData(
                success=True,
                message="Session created successfully.",
                result={"user_id": str(user.id)},
            ),
            session_token,
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
        default_message="No se pudo iniciar sesion con GitHub.",
        default_code="LOGIN_GITHUB_ERROR",
    )
    async def login_with_github(self, data: GitHubOAuthRequest) -> Union[SucessWithData, ErrorResponse]:
        user, oauth_account = await self.user_service.authenticate_with_github(data)
        return SucessWithData(
            success=True,
            message="GitHub login processed successfully.",
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
