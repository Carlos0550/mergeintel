"""Mail payload schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class EmailPayload(BaseModel):
    """Provider-agnostic email payload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    to: list[str]
    subject: str
    html: str | None = None
    text: str | None = None

    @field_validator("to")
    @classmethod
    def validate_recipients(cls, value: list[str]) -> list[str]:
        """Ensure at least one recipient is present."""

        recipients = [recipient for recipient in value if recipient]
        if not recipients:
            raise ValueError("At least one recipient is required.")
        return recipients

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        """Ensure subject is not empty."""

        if not value:
            raise ValueError("Subject is required.")
        return value

    @model_validator(mode="after")
    def validate_body(self) -> "EmailPayload":
        """Require at least one body representation."""

        if not self.html and not self.text:
            raise ValueError("At least one of 'html' or 'text' must be provided.")
        return self
