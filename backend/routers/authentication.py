"""Authentication router definitions."""

from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.authentication import UserController
from backend.dependencies import get_db_session, get_mail_service
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest, GitHubOAuthRequest
from backend.services.mail import MailService


router = APIRouter(prefix="/auth", tags=["authentication & User management"])


def _parse_github_state(state: str | None) -> tuple[str, UUID | None]:
    """Resolve the callback action from the OAuth state value."""

    if state is None or state == "create":
        return "create", None

    if state.startswith("link:"):
        raw_user_id = state.removeprefix("link:").strip()
        if not raw_user_id:
            raise ValueError("Missing user_id in OAuth state")
        return "link", UUID(raw_user_id)

    raise ValueError("Invalid OAuth state")


def _build_github_state(mode: str, user_id: UUID | None) -> str:
    """Build the OAuth state value used by the GitHub callback."""

    if mode == "create":
        return "create"

    if mode == "link":
        if user_id is None:
            raise ValueError("user_id is required when mode=link")
        
        return f"link:{user_id}"

    raise ValueError("mode must be 'create' or 'link'")


@router.post(
    "/user/new",
    response_model=None,
    responses={200: {"model": SucessWithData}, 400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def create_user(
    data: CreateUserRequest,
    db: AsyncSession = Depends(get_db_session),
    mail_service: MailService = Depends(get_mail_service),
):
    controller = UserController(db=db, mail_service=mail_service)
    result = await controller.create_user(data)
    if isinstance(result, ErrorResponse):
        return JSONResponse(
            content=result.model_dump(),
            status_code=result.status_code,
        )
    return result


@router.get(
    "/github/start",
    response_model=None,
    responses={
        200: {"model": SucessWithData},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def start_github_oauth(
    request: Request,
    mode: str = Query(default="create"),
    user_id: UUID | None = Query(default=None),
):
    from backend.config import settings

    if not settings.GITHUB_CLIENT_ID:
        result = ErrorResponse(
            success=False,
            message="Falta configurar GITHUB_CLIENT_ID.",
            err="Missing GITHUB_CLIENT_ID",
            err_code="GITHUB_OAUTH_NOT_CONFIGURED",
            status_code=500,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    try:
        state = _build_github_state(mode, user_id)
    except ValueError as exc:
        result = ErrorResponse(
            success=False,
            message="Los parametros para iniciar OAuth son invalidos.",
            err=str(exc),
            err_code="GITHUB_START_INVALID",
            status_code=400,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    redirect_uri = str(request.url_for("github_callback"))
    query = urlencode(
        {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
    )
    authorization_url = f"https://github.com/login/oauth/authorize?{query}"

    return SucessWithData(
        success=True,
        message="GitHub OAuth URL generated successfully.",
        result={
            "authorization_url": authorization_url,
            "redirect_uri": redirect_uri,
            "state": state,
            "mode": mode,
        },
    )


@router.get(
    "/github/callback",
    name="github_callback",
    response_model=None,
    responses={
        200: {"model": SucessWithData},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def github_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default="create"),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    mail_service: MailService = Depends(get_mail_service),
):
    if error:
        result = ErrorResponse(
            success=False,
            message="GitHub devolvio un error en el callback.",
            err=error_description or error,
            err_code="GITHUB_CALLBACK_ERROR",
            status_code=400,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    if not code:
        result = ErrorResponse(
            success=False,
            message="GitHub no devolvio un code en el callback.",
            err="Missing code query parameter",
            err_code="GITHUB_CODE_MISSING",
            status_code=400,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    try:
        action, user_id = _parse_github_state(state)
    except ValueError as exc:
        result = ErrorResponse(
            success=False,
            message="El parametro state del callback es invalido.",
            err=str(exc),
            err_code="GITHUB_STATE_INVALID",
            status_code=400,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    controller = UserController(db=db, mail_service=mail_service)
    payload = GitHubOAuthRequest(
        code=code,
        redirect_uri=str(request.url_for("github_callback")),
    )

    if action == "link":
        result = await controller.link_github_account(user_id, payload)
    else:
        result = await controller.create_user_with_github(payload)

    if isinstance(result, ErrorResponse):
        return JSONResponse(
            content=result.model_dump(),
            status_code=result.status_code,
        )
    return result
