"""User ORM models."""

from __future__ import annotations

from .base import BaseModel
from enum import Enum as PyEnum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column


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


def enum_values(enum_class: type[PyEnum]) -> list[str]:
    """Return persisted values for SQLAlchemy enums."""

    return [member.value for member in enum_class]


class User(BaseModel):
    """User account model."""

    __tablename__ = "user"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(Text, nullable=False)
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
