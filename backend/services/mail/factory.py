"""Mail service factory helpers."""

from __future__ import annotations

from backend.config import Settings

from .base import MailService
from .providers import FastAPIMailService, ResendMailService


def build_mail_service(current_settings: Settings) -> MailService:
    """Build the mail service for the configured environment."""

    if current_settings.APP_ENV.lower() == "production":
        if not current_settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is required when APP_ENV is set to 'production'.")
        return ResendMailService(current_settings)
    return FastAPIMailService(current_settings)


def validate_mail_settings(current_settings: Settings) -> None:
    """Fail fast when the active mail configuration is invalid."""

    build_mail_service(current_settings)
