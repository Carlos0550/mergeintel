"""Authentication router definitions."""

from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.controllers.authentication import UserController
from backend.dependencies import get_current_user, get_db_session, get_mail_service, get_optional_current_user
from backend.schemas.base import ErrorResponse, SucessWithData
from backend.schemas.user_managment import CreateUserRequest, CurrentUser, GitHubOAuthRequest, LoginRequest
from backend.services.mail import MailService


router = APIRouter(prefix="/auth", tags=["authentication & User management"])
SESSION_COOKIE_NAME = "mergeintel_session"


def _parse_github_state(state: str | None) -> tuple[str, UUID | None]:
    """Resolve the callback action from the OAuth state value."""

    if state is None or state == "create":
        return "create", None

    if state == "login":
        return "login", None

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

    if mode == "login":
        return "login"

    if mode == "link":
        if user_id is None:
            raise ValueError("user_id is required when mode=link")
        
        return f"link:{user_id}"

    raise ValueError("mode must be 'create', 'login' or 'link'")


def _set_session_cookie(response: JSONResponse, session_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 30,
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, samesite="lax")


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


@router.post(
    "/login",
    response_model=None,
    responses={200: {"model": SucessWithData}, 401: {"model": ErrorResponse}},
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
    mail_service: MailService = Depends(get_mail_service),
):
    controller = UserController(db=db, mail_service=mail_service)
    result = await controller.login(data)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    payload, session_token = result
    response = JSONResponse(content=payload.model_dump(), status_code=200)
    _set_session_cookie(response, session_token)
    return response


@router.get(
    "/me",
    response_model=None,
    responses={200: {"model": SucessWithData}, 401: {"model": ErrorResponse}},
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    mail_service: MailService = Depends(get_mail_service),
):
    controller = UserController(db=db, mail_service=mail_service)
    result = await controller.get_current_user_data(current_user)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)
    return result


@router.post(
    "/logout",
    response_model=None,
    responses={200: {"model": SucessWithData}, 401: {"model": ErrorResponse}},
)
async def logout(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db_session),
    mail_service: MailService = Depends(get_mail_service),
):
    if not session_token:
        result = ErrorResponse(
            success=False,
            message="No hay una sesion activa.",
            err="Missing session cookie",
            err_code="AUTH_REQUIRED",
            status_code=401,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    controller = UserController(db=db, mail_service=mail_service)
    result = await controller.logout(session_token)
    if isinstance(result, ErrorResponse):
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    response = JSONResponse(content=result.model_dump(), status_code=200)
    _clear_session_cookie(response)
    return response


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
    current_user: CurrentUser | None = Depends(get_optional_current_user),
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

    if mode == "link" and current_user is None:
        result = ErrorResponse(
            success=False,
            message="Debes iniciar sesion antes de enlazar GitHub.",
            err="Missing authenticated user for link mode",
            err_code="AUTH_REQUIRED",
            status_code=401,
        )
        return JSONResponse(content=result.model_dump(), status_code=result.status_code)

    try:
        state_user_id = current_user.id if mode == "link" and current_user else user_id
        state = _build_github_state(mode, UUID(str(state_user_id)) if state_user_id else None)
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
            "scope": "read:user user:email repo",
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
    elif action == "login":
        result = await controller.login_with_github(payload)
    else:
        result = await controller.create_user_with_github(payload)

    if isinstance(result, ErrorResponse):
        return JSONResponse(
            content=result.model_dump(),
            status_code=result.status_code,
        )

    session_result = await controller.create_session_for_user(UUID(str(result.result["id"])))
    if isinstance(session_result, ErrorResponse):
        return JSONResponse(content=session_result.model_dump(), status_code=session_result.status_code)

    _, session_token = session_result
    response = JSONResponse(content=result.model_dump(), status_code=200)
    _set_session_cookie(response, session_token)
    return response
