"""Mail provider implementations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.config import Settings

from .base import MailDeliveryError, MailService
from .schemas import EmailPayload

logger = logging.getLogger(__name__)


def format_sender(mail_from: str, mail_from_name: str) -> str:
    """Return a formatted sender string for providers that need a single value."""

    if mail_from_name:
        return f"{mail_from_name} <{mail_from}>"
    return mail_from


class FastAPIMailService(MailService):
    """Mail service backed by fastapi-mail."""

    def __init__(
        self,
        current_settings: Settings,
        *,
        mailer: Any | None = None,
        connection_config: Any | None = None,
    ) -> None:
        self.settings = current_settings
        self.connection_config = connection_config or self._build_connection_config(current_settings)
        self.mailer = mailer or self._build_mailer(self.connection_config)

    @staticmethod
    def _build_connection_config(current_settings: Settings) -> Any:
        """Build the fastapi-mail connection config."""

        from fastapi_mail import ConnectionConfig

        return ConnectionConfig(
            MAIL_USERNAME=current_settings.MAIL_USERNAME,
            MAIL_PASSWORD=current_settings.MAIL_PASSWORD,
            MAIL_FROM=current_settings.MAIL_FROM,
            MAIL_PORT=current_settings.MAIL_PORT,
            MAIL_SERVER=current_settings.MAIL_SERVER,
            MAIL_FROM_NAME=current_settings.MAIL_FROM_NAME,
            MAIL_STARTTLS=current_settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=current_settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=current_settings.MAIL_USE_CREDENTIALS,
            VALIDATE_CERTS=current_settings.MAIL_VALIDATE_CERTS,
        )

    @staticmethod
    def _build_mailer(connection_config: Any) -> Any:
        """Build the fastapi-mail sender."""

        from fastapi_mail import FastMail

        return FastMail(connection_config)

    @staticmethod
    def _build_message_kwargs(payload: EmailPayload) -> dict[str, Any]:
        """Translate the generic payload into fastapi-mail fields."""

        body = payload.html if payload.html is not None else payload.text
        subtype = "html" if payload.html is not None else "plain"
        return {
            "subject": payload.subject,
            "recipients": payload.to,
            "body": body,
            "subtype": subtype,
        }

    async def send_email(self, payload: EmailPayload) -> None:
        from fastapi_mail import MessageSchema, MessageType

        message_kwargs = self._build_message_kwargs(payload)
        subtype = MessageType.html if message_kwargs["subtype"] == "html" else MessageType.plain
        message = MessageSchema(
            subject=message_kwargs["subject"],
            recipients=message_kwargs["recipients"],
            body=message_kwargs["body"],
            subtype=subtype,
        )

        try:
            await self.mailer.send_message(message)
            logger.info(
                "Email sent through development SMTP mailbox",
                extra={
                    "provider": "fastapi-mail",
                    "mail_ui_url": "http://localhost:8025",
                    "mail_server": self.settings.MAIL_SERVER,
                    "mail_port": self.settings.MAIL_PORT,
                    "recipients": payload.to,
                    "subject": payload.subject,
                },
            )
        except Exception as exc:  # pragma: no cover - provider error surface
            logger.exception("Failed to send email with fastapi-mail")
            raise MailDeliveryError("fastapi-mail failed to send the email.") from exc


class ResendMailService(MailService):
    """Mail service backed by Resend."""

    def __init__(
        self,
        current_settings: Settings,
        *,
        resend_module: Any | None = None,
        sender: Any | None = None,
    ) -> None:
        self.settings = current_settings
        self.resend_module = resend_module or self._configure_resend_module(current_settings)
        self.sender = sender or self.resend_module.Emails

    @staticmethod
    def _configure_resend_module(current_settings: Settings) -> Any:
        """Configure and return the resend module."""

        import resend

        resend.api_key = current_settings.RESEND_API_KEY
        return resend

    def _build_message_params(self, payload: EmailPayload) -> dict[str, Any]:
        """Translate the generic payload into Resend fields."""

        params: dict[str, Any] = {
            "from": format_sender(self.settings.MAIL_FROM, self.settings.MAIL_FROM_NAME),
            "to": payload.to,
            "subject": payload.subject,
        }
        if payload.html is not None:
            params["html"] = payload.html
        if payload.text is not None:
            params["text"] = payload.text
        return params

    async def send_email(self, payload: EmailPayload) -> None:
        params = self._build_message_params(payload)

        try:
            await asyncio.to_thread(self.sender.send, params)
        except Exception as exc:  # pragma: no cover - provider error surface
            logger.exception("Failed to send email with Resend")
            raise MailDeliveryError("Resend failed to send the email.") from exc
