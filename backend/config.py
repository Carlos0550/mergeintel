"""Application configuration for MergeIntel."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
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
    GITHUB_TOKEN_ENCRYPTION_KEY: str | None = None
    AI_PROVIDER_API_KEY: str | None = None
    AI_PROVIDER: str = "groq"
    AI_MODEL: str | None = None
    DATABASE_URL: str
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "America/Argentina/Buenos_Aires"
    FRONTEND_BASE_URL: str = "http://localhost:3000"
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

    @field_validator("GITHUB_API_BASE_URL", mode="before")
    @classmethod
    def normalize_github_api_base_url(cls, value: str | None) -> str:
        """Fallback to the default GitHub API URL when the env value is blank."""

        normalized = (value or "").strip()
        return normalized or "https://api.github.com"

    @field_validator("AI_PROVIDER", mode="before")
    @classmethod
    def normalize_ai_provider(cls, value: str | None) -> str:
        """Normalize the configured AI provider."""

        normalized = (value or "").strip().lower()
        return normalized or "groq"

    @field_validator("AI_MODEL", mode="before")
    @classmethod
    def normalize_ai_model(cls, value: str | None) -> str | None:
        """Treat blank AI model values as unset so provider defaults can apply."""

        normalized = (value or "").strip()
        return normalized or None

    @field_validator("FRONTEND_BASE_URL", mode="before")
    @classmethod
    def normalize_frontend_base_url(cls, value: str | None) -> str:
        """Fallback to the local frontend URL when unset and remove trailing slash."""

        normalized = (value or "").strip().rstrip("/")
        return normalized or "http://localhost:3000"

    @field_validator("AI_PROVIDER_API_KEY", "GITHUB_TOKEN_ENCRYPTION_KEY", mode="before")
    @classmethod
    def normalize_optional_secret(cls, value: str | None) -> str | None:
        """Treat blank secret env vars as missing values."""

        normalized = (value or "").strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_provider_settings(self) -> Settings:
        """Validate provider-specific configuration without spreading env rules elsewhere."""

        supported_providers = {"anthropic", "openai", "groq", "ollama"}
        if self.AI_PROVIDER not in supported_providers:
            raise ValueError(f"Unsupported AI provider: {self.AI_PROVIDER}")

        if (self.GITHUB_CLIENT_ID or self.GITHUB_CLIENT_SECRET) and not self.GITHUB_TOKEN_ENCRYPTION_KEY:
            raise ValueError("GITHUB_TOKEN_ENCRYPTION_KEY is required when GitHub OAuth is enabled.")

        return self


settings = Settings()
