"""User authentication and GitHub OAuth services."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.exceptions import AppError
from backend.models.user import OAuthAccount, OauthProviders, User, UserRole, UserStatus
from backend.schemas.user_managment import CreateUserRequest, GitHubOAuthRequest, LoginRequest
from backend.services.github import GitHubClient
from backend.services.mail import EmailPayload, MailService, render_html_template
from backend.utils.security import encrypt_secret, hash_string, verify_string
from backend.utils.text import capitalize_words


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GitHubIdentity:
    provider_user_id: str
    provider_login: str
    email: str
    name: str
    access_token: str


class UserService:
    """Application service for local and GitHub-backed authentication flows."""

    def __init__(self, session: AsyncSession, mail_service: MailService) -> None:
        self.session = session
        self.mail_service = mail_service

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
            logger.exception("Failed to create user", extra={"operation": "create_user", "email": data.email})
            raise

    async def authenticate_user(self, data: LoginRequest) -> User:
        user = await self.get_user_by_email(data.email)
        if user is None or not user.password:
            raise AppError(
                "Las credenciales no son validas.",
                err_code="INVALID_CREDENTIALS",
                status_code=401,
            )
        if not verify_string(data.password, user.password):
            raise AppError(
                "Las credenciales no son validas.",
                err_code="INVALID_CREDENTIALS",
                status_code=401,
            )
        if user.status != UserStatus.ACTIVE:
            raise AppError(
                "El usuario no se encuentra activo.",
                err_code="USER_INACTIVE",
                status_code=403,
            )
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user_with_github(self, data: GitHubOAuthRequest) -> tuple[User, OAuthAccount]:
        identity = await self._resolve_github_identity(data)

        existing_oauth = await self._get_github_oauth_account(identity.provider_user_id)
        if existing_oauth is not None:
            raise AppError(
                "La cuenta de GitHub ya esta registrada en MergeIntel.",
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
                extra={"operation": "create_user_with_github", "email": identity.email},
            )
            raise
        return user, oauth_account

    async def link_github_account(self, user_id: UUID, data: GitHubOAuthRequest) -> tuple[User, OAuthAccount]:
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise AppError("El usuario no existe.", err_code="USER_NOT_FOUND", status_code=404)

        identity = await self._resolve_github_identity(data)
        existing_oauth = await self._get_github_oauth_account(identity.provider_user_id)
        if existing_oauth is not None:
            if existing_oauth.user_id == user.id:
                existing_oauth.provider_login = identity.provider_login
                existing_oauth.access_token = self._encrypt_github_token(identity.access_token)
                await self.session.commit()
                return user, existing_oauth
            raise AppError(
                "La cuenta de GitHub ya esta enlazada a otro usuario.",
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

        return user, await self._create_github_link(user, identity)

    async def authenticate_with_github(self, data: GitHubOAuthRequest) -> tuple[User, OAuthAccount]:
        """Authenticate an existing MergeIntel user through a previously linked GitHub account."""

        identity = await self._resolve_github_identity(data)
        existing_oauth = await self._get_github_oauth_account(identity.provider_user_id)
        if existing_oauth is None:
            existing_user = await self.get_user_by_email(identity.email)
            if existing_user is not None:
                raise AppError(
                    "Tu usuario existe pero no tiene GitHub enlazado. Usa el flujo de enlace primero.",
                    err_code="GITHUB_ACCOUNT_NOT_LINKED",
                    status_code=409,
                )
            raise AppError(
                "No existe una cuenta registrada con ese GitHub. Usa el flujo de registro primero.",
                err_code="GITHUB_ACCOUNT_NOT_REGISTERED",
                status_code=404,
            )

        user = await self.get_user_by_id(existing_oauth.user_id)
        if user is None:
            raise AppError(
                "La cuenta enlazada ya no tiene un usuario valido.",
                err_code="USER_NOT_FOUND",
                status_code=404,
            )

        existing_oauth.provider_login = identity.provider_login
        existing_oauth.access_token = self._encrypt_github_token(identity.access_token)
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                "Failed to refresh GitHub token during login",
                extra={"operation": "authenticate_with_github", "user_id": str(user.id)},
            )
            raise

        return user, existing_oauth

    async def _resolve_github_identity(self, data: GitHubOAuthRequest) -> GitHubIdentity:
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise AppError(
                "Falta configurar GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET.",
                err_code="GITHUB_OAUTH_NOT_CONFIGURED",
                status_code=500,
            )

        async with GitHubClient(base_url=settings.GITHUB_API_BASE_URL) as github_client:
            access_token = await github_client.exchange_code_for_token(code=data.code, redirect_uri=data.redirect_uri)

        async with GitHubClient(access_token=access_token, base_url=settings.GITHUB_API_BASE_URL) as github_client:
            identity = await self._build_identity(github_client, access_token)

        return identity

    async def _build_identity(self, github_client: GitHubClient, access_token: str) -> GitHubIdentity:
        user_payload = await github_client.get_current_user()
        provider_user_id = str(user_payload.get("id") or "").strip()
        provider_login = str(user_payload.get("login") or "").strip()
        if not provider_user_id or not provider_login:
            raise AppError(
                "GitHub devolvio un perfil incompleto.",
                err_code="GITHUB_USER_INVALID",
                status_code=502,
            )

        email = str(user_payload.get("email") or "").strip().lower()
        if not email:
            email = await self._fetch_primary_email(github_client)
        if not email:
            raise AppError(
                "No se pudo obtener un email valido desde GitHub.",
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

    async def _fetch_primary_email(self, github_client: GitHubClient) -> str:
        emails = await github_client.get_current_user_emails()
        primary_verified = next(
            (
                str(item.get("email") or "").strip().lower()
                for item in emails
                if item.get("primary") and item.get("verified") and item.get("email")
            ),
            "",
        )
        if primary_verified:
            return primary_verified
        return next(
            (
                str(item.get("email") or "").strip().lower()
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

    async def _get_user_oauth_account(self, user_id: UUID, provider: OauthProviders) -> OAuthAccount | None:
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
                EmailPayload(to=[user.email], subject="Welcome to MergeIntel", html=html_content)
            )
        except Exception:
            logger.exception("Failed to send welcome email", extra={"user_id": str(user.id), "email": user.email})

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
            access_token=self._encrypt_github_token(identity.access_token),
        )
        self.session.add(oauth_account)
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            logger.exception(
                "Failed to link GitHub account",
                extra={"operation": "link_github_account", "user_id": str(user.id)},
            )
            raise

        if send_welcome_email:
            await self._send_welcome_email(user)
        return oauth_account

    def _encrypt_github_token(self, token: str) -> str:
        return encrypt_secret(token, settings.GITHUB_TOKEN_ENCRYPTION_KEY or "")

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip().lower()
