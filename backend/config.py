"""Application configuration for MergeIntel."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_WEBHOOK_SECRET: str | None = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_PROVIDER: str = "anthropic"
    AI_MODEL: str | None = "claude-sonnet-4-20250514"
    DATABASE_URL: str
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "America/Argentina/Buenos_Aires"
    MAIL_FROM: str = "no-reply@example.com"
    MAIL_FROM_NAME: str = "MergeIntel"
    MAIL_SERVER: str = "mailpit"
    MAIL_PORT: int = 1025
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = False
    MAIL_USE_CREDENTIALS: bool = False
    MAIL_VALIDATE_CERTS: bool = False
    RESEND_API_KEY: str | None = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_ENABLE_STDOUT: bool = True
    LOG_ENABLE_FILE: bool = True
    LOG_FILE_PATH: str = "/var/log/mergeintel/app.log"
    LOG_FILE_MAX_BYTES: int = Field(default=10_485_760, ge=1)
    LOG_FILE_BACKUP_COUNT: int = Field(default=5, ge=0)

    @field_validator("APP_TIMEZONE")
    @classmethod
    def validate_app_timezone(cls, value: str) -> str:
        """Ensure the configured timezone exists."""

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid timezone: {value}") from exc
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure the configured log level is supported by stdlib logging."""

        normalized = value.upper()
        if normalized not in logging.getLevelNamesMapping():
            raise ValueError(f"Invalid log level: {value}")
        return normalized

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        """Ensure the configured log format is supported."""

        normalized = value.lower()
        if normalized not in {"json", "text"}:
            raise ValueError(f"Invalid log format: {value}")
        return normalized


settings = Settings()
