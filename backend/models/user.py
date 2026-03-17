"""User ORM models."""

from __future__ import annotations

from uuid import UUID

from .base import BaseModel
from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


class UserRole(PyEnum):
    """Available user roles."""

    ADMIN = "admin"
    USER = "user"


class UserStatus(PyEnum):
    """Available user account statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BANNED = "banned"


class OauthProviders(PyEnum):
    GITHUB = "github"
    NO_PROVIDER = "no_provider"
    GOOGLE = "google"


def enum_values(enum_class: type[PyEnum]) -> list[str]:
    """Return persisted values for SQLAlchemy enums."""

    return [member.value for member in enum_class]


class User(BaseModel):
    """User account model."""

    __tablename__ = "user"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=enum_values),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", values_callable=enum_values),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )


class OAuthAccount(BaseModel):
    __tablename__ = "OAuthAccount"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[OauthProviders] = mapped_column(
        Enum(OauthProviders, name="oauth_providers_enum", values_callable=enum_values),
        nullable=False,
        default=OauthProviders.NO_PROVIDER,
        server_default=OauthProviders.NO_PROVIDER.value,
    )

    provider_user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    provider_login: Mapped[str | None] = mapped_column(
        String(255), nullable=True  # ej: "carlos-dev" en GitHub
    )

    access_token: Mapped[str | None] = mapped_column(
        Text, nullable=True  # token para llamar a la API de GitHub
    )

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        # Un usuario no puede tener dos cuentas del mismo proveedor
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )
