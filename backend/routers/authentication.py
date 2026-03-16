"""Authentication router definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.authentication import UserController
from backend.dependencies import get_db_session
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest


router = APIRouter(prefix="/auth", tags=["authentication & User management"])


@router.post(
    "/user/new",
    response_model=None,
    responses={200: {"model": SucessWithData}, 400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def create_user(
    data: CreateUserRequest,
    db: AsyncSession = Depends(get_db_session),
):
    controller = UserController(db=db)
    result = await controller.create_user(data)
    if isinstance(result, ErrorResponse):
        return JSONResponse(
            content=result.model_dump(),
            status_code=result.status_code,
        )
    return result
