from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from backend.models.user import UserRole, UserStatus


class OAuthAccountSummary(BaseModel):
    provider: str = Field(..., description="OAuth provider name")
    provider_login: str | None = Field(default=None, description="OAuth provider username/login")


class CurrentUser(BaseModel):
    id: str = Field(..., description="The id of the user")
    name: str = Field(..., description="The name of the user")
    email: str = Field(..., description="The email of the user")
    role: UserRole = Field(..., description="The role of the user")
    status: UserStatus = Field(..., description="The status of the user")
    created_at: datetime | None = Field(default=None, description="The account creation timestamp")
    oauth_accounts: list[OAuthAccountSummary] = Field(
        default_factory=list,
        description="Linked OAuth accounts for the user",
    )
    github_account: OAuthAccountSummary | None = Field(default=None, description="Linked GitHub account if present")
    github_login: str | None = Field(default=None, description="Linked GitHub username/login")

class CreateUserRequest(BaseModel):
    name: str = Field(..., description="The name of the user")
    email: str = Field(..., description="The email of the user")
    password: str = Field(..., description="The password of the user")

    @field_validator("email", mode="before")
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.strip().lower()

    @field_validator("password", mode="before")
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v
    
    @field_validator("name", mode="before")
    def validate_name(cls, v: str) -> str:
        return v.strip().lower()


class GitHubOAuthRequest(BaseModel):
    code: str = Field(..., description="GitHub OAuth authorization code")
    redirect_uri: str | None = Field(
        default=None,
        description="Redirect URI used when exchanging the authorization code",
    )

    @field_validator("code", mode="before")
    def validate_code(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("GitHub code is required")
        return value

    @field_validator("redirect_uri", mode="before")
    def validate_redirect_uri(cls, v: str | None) -> str | None:
        if v is None:
            return None
        value = v.strip()
        return value or None


class LoginRequest(BaseModel):
    email: str = Field(..., description="The user email")
    password: str = Field(..., description="The user password")

    @field_validator("email", mode="before")
    def normalize_email(cls, v: str) -> str:
        value = v.strip().lower()
        if "@" not in value:
            raise ValueError("Invalid email")
        return value

    @field_validator("password", mode="before")
    def normalize_password(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Password is required")
        return value
