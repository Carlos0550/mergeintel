"""User authentication and management service using SQLAlchemy ORM."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from uuid import UUID

import httpx
from backend.config import settings
from backend.exceptions import AppError
from backend.models.user import User, UserRole, UserStatus
from backend.models.user import OAuthAccount, OauthProviders
from backend.services.mail import EmailPayload, MailService, render_html_template
from backend.schemas.user_managment import CreateUserRequest, CurrentUser, GitHubOAuthRequest
from backend.utils.security import hash_string
from backend.utils.text import capitalize_words
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GitHubIdentity:
    provider_user_id: str
    provider_login: str
    email: str
    name: str
    access_token: str


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
            await self._send_welcome_email(user)
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
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user by id."""

        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user_with_github(self, data: GitHubOAuthRequest) -> tuple[User, OAuthAccount]:
        """Create a new local user from GitHub or auto-link by email when possible."""

        identity = await self._resolve_github_identity(data)

        existing_oauth = await self._get_github_oauth_account(identity.provider_user_id)
        if existing_oauth is not None:
            raise AppError(
                "La cuenta de GitHub ya está registrada en MergeIntel.",
                err_code="GITHUB_ACCOUNT_ALREADY_REGISTERED",
                status_code=409,
            )

        existing_user = await self.get_user_by_email(identity.email)
        if existing_user is not None:
            existing_user_link = await self._get_user_oauth_account(existing_user.id, OauthProviders.GITHUB)
            if existing_user_link is not None:
                raise AppError(
                    "El usuario con ese email ya tiene una cuenta de GitHub enlazada.",
                    err_code="USER_ALREADY_HAS_GITHUB",
                    status_code=409,
                )
            return await self._create_github_link(existing_user, identity)

        user = User(
            name=self._normalize_name(identity.name),
            email=identity.email,
            password=None,
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        self.session.add(user)
        try:
            oauth_account = await self._create_github_link(user, identity, send_welcome_email=False)
            await self._send_welcome_email(user)
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                "Failed to create GitHub user",
                extra={
                    "operation": "create_user_with_github",
                    "github_user_id": identity.provider_user_id,
                    "github_login": identity.provider_login,
                    "request_user_email": identity.email,
                },
            )
            raise

        return user, oauth_account

    async def link_github_account(self, user_id: UUID, data: GitHubOAuthRequest) -> tuple[User, OAuthAccount]:
        """Link a GitHub account to an existing local user."""

        user = await self.get_user_by_id(user_id)
        if user is None:
            raise AppError(
                "El usuario no existe.",
                err_code="USER_NOT_FOUND",
                status_code=404,
            )

        identity = await self._resolve_github_identity(data)

        existing_oauth = await self._get_github_oauth_account(identity.provider_user_id)
        if existing_oauth is not None:
            if existing_oauth.user_id == user.id:
                existing_oauth.provider_login = identity.provider_login
                existing_oauth.access_token = identity.access_token
                try:
                    await self.session.commit()
                except SQLAlchemyError:
                    await self.session.rollback()
                    logger.exception(
                        "Failed to refresh existing GitHub link",
                        extra={
                            "operation": "link_github_account_refresh",
                            "user_id": str(user.id),
                            "github_user_id": identity.provider_user_id,
                        },
                    )
                    raise
                return user, existing_oauth

            raise AppError(
                "La cuenta de GitHub ya está enlazada a otro usuario.",
                err_code="GITHUB_ACCOUNT_ALREADY_LINKED",
                status_code=409,
            )

        existing_user_link = await self._get_user_oauth_account(user.id, OauthProviders.GITHUB)
        if existing_user_link is not None:
            raise AppError(
                "El usuario ya tiene una cuenta de GitHub enlazada.",
                err_code="USER_ALREADY_HAS_GITHUB",
                status_code=409,
            )

        if user.email != identity.email:
            logger.info(
                "GitHub email differs from user email during link",
                extra={
                    "operation": "link_github_account",
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "github_email": identity.email,
                },
            )

        oauth_account = await self._create_github_link(user, identity)
        return user, oauth_account

    async def _resolve_github_identity(self, data: GitHubOAuthRequest) -> GitHubIdentity:
        """Exchange the OAuth code and fetch the GitHub profile."""

        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise AppError(
                "Falta configurar GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET.",
                err_code="GITHUB_OAUTH_NOT_CONFIGURED",
                status_code=500,
            )

        access_token = await self._exchange_github_code_for_token(data)
        user_payload = await self._fetch_github_user(access_token)

        provider_user_id = str(user_payload["id"])
        provider_login = str(user_payload["login"]).strip()
        email = (user_payload.get("email") or "").strip().lower()
        if not email:
            email = await self._fetch_primary_github_email(access_token)
        if not email:
            raise AppError(
                "No se pudo obtener un email válido desde GitHub.",
                err_code="GITHUB_EMAIL_NOT_AVAILABLE",
                status_code=400,
            )

        display_name = str(user_payload.get("name") or provider_login).strip() or provider_login
        return GitHubIdentity(
            provider_user_id=provider_user_id,
            provider_login=provider_login,
            email=email,
            name=display_name,
            access_token=access_token,
        )

    async def _exchange_github_code_for_token(self, data: GitHubOAuthRequest) -> str:
        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": data.code,
        }
        if data.redirect_uri:
            payload["redirect_uri"] = data.redirect_uri

        headers = {
            "Accept": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data=payload,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.exception("GitHub token exchange failed")
                raise AppError(
                    "No se pudo intercambiar el code de GitHub por un token.",
                    err_code="GITHUB_TOKEN_EXCHANGE_FAILED",
                    status_code=502,
                ) from exc

        token_payload = response.json()
        access_token = str(token_payload.get("access_token") or "").strip()
        if not access_token:
            raise AppError(
                "GitHub no devolvió un access token válido.",
                err_code="GITHUB_ACCESS_TOKEN_MISSING",
                status_code=400,
            )
        return access_token

    async def _fetch_github_user(self, access_token: str) -> dict:
        async with httpx.AsyncClient(
            base_url=settings.GITHUB_API_BASE_URL,
            timeout=20.0,
            headers=self._github_api_headers(access_token),
        ) as client:
            try:
                response = await client.get("/user")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.exception("GitHub user fetch failed")
                raise AppError(
                    "No se pudo obtener el perfil del usuario en GitHub.",
                    err_code="GITHUB_USER_FETCH_FAILED",
                    status_code=502,
                ) from exc

        payload = response.json()
        if "id" not in payload or "login" not in payload:
            raise AppError(
                "GitHub devolvió un perfil incompleto.",
                err_code="GITHUB_USER_INVALID",
                status_code=502,
            )
        return payload

    async def _fetch_primary_github_email(self, access_token: str) -> str:
        async with httpx.AsyncClient(
            base_url=settings.GITHUB_API_BASE_URL,
            timeout=20.0,
            headers=self._github_api_headers(access_token),
        ) as client:
            try:
                response = await client.get("/user/emails")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.exception("GitHub email fetch failed")
                raise AppError(
                    "No se pudo obtener el email del usuario desde GitHub.",
                    err_code="GITHUB_EMAIL_FETCH_FAILED",
                    status_code=502,
                ) from exc

        emails = response.json()
        if not isinstance(emails, list):
            return ""

        primary_verified = next(
            (
                item.get("email", "").strip().lower()
                for item in emails
                if item.get("primary") and item.get("verified") and item.get("email")
            ),
            "",
        )
        if primary_verified:
            return primary_verified

        return next(
            (
                item.get("email", "").strip().lower()
                for item in emails
                if item.get("verified") and item.get("email")
            ),
            "",
        )

    async def _get_github_oauth_account(self, provider_user_id: str) -> OAuthAccount | None:
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == OauthProviders.GITHUB,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_oauth_account(
        self,
        user_id: UUID,
        provider: OauthProviders,
    ) -> OAuthAccount | None:
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def _send_welcome_email(self, user: User) -> None:
        html_content = render_html_template(
            "backend/templates/welcome.html",
            user_name=capitalize_words(user.name),
            user_email=user.email,
        )
        try:
            await self.mail_service.send_email(
                EmailPayload(
                    to=[user.email],
                    subject="Welcome to MergeIntel",
                    html=html_content,
                )
            )
        except Exception:
            logger.exception(
                "Failed to send welcome email",
                extra={
                    "operation": "send_welcome_email",
                    "user_id": str(user.id),
                    "user_email": user.email,
                },
            )

    async def _create_github_link(
        self,
        user: User,
        identity: GitHubIdentity,
        *,
        send_welcome_email: bool = False,
    ) -> OAuthAccount:
        oauth_account = OAuthAccount(
            user=user,
            provider=OauthProviders.GITHUB,
            provider_user_id=identity.provider_user_id,
            provider_login=identity.provider_login,
            access_token=identity.access_token,
        )
        self.session.add(oauth_account)
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                "Failed to link GitHub account",
                extra={
                    "operation": "link_github_account",
                    "user_id": str(user.id),
                    "github_user_id": identity.provider_user_id,
                },
            )
            raise

        if send_welcome_email:
            await self._send_welcome_email(user)

        return oauth_account

 

    def _github_api_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
