"""Mail service contracts and shared errors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import EmailPayload


class MailDeliveryError(RuntimeError):
    """Raised when a mail provider cannot deliver an email."""


class MailService(ABC):
    """Abstract mail service used by the rest of the application."""

    @abstractmethod
    async def send_email(self, payload: EmailPayload) -> None:
        """Send an email through the configured provider."""
