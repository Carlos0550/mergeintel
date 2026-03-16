"""Authentication controllers."""

from __future__ import annotations

import logging
from typing import Union

from backend.services.mail import MailService
from backend.services.authentication import UserService
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest
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
