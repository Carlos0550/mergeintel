"""Mail service abstractions and providers."""

from .base import MailDeliveryError, MailService
from .factory import build_mail_service, validate_mail_settings
from .providers import FastAPIMailService, ResendMailService
from .schemas import EmailPayload
from .templates import render_html_template

__all__ = [
    "EmailPayload",
    "FastAPIMailService",
    "MailDeliveryError",
    "MailService",
    "ResendMailService",
    "build_mail_service",
    "render_html_template",
    "validate_mail_settings",
]
