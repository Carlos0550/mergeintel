"""Chat persistence models for contextual PR conversations."""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel
from backend.models.user import enum_values


class ChatRole(PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(BaseModel):
    """Stored chat session tied to an analysis and a user."""

    __tablename__ = "chat_session"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("pr_analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)

    analysis = relationship("PRAnalysis", back_populates="chat_sessions")
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(BaseModel):
    """Stored chat message exchanged inside a chat session."""

    __tablename__ = "chat_message"

    session_id: Mapped[UUID] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[ChatRole] = mapped_column(
        Enum(ChatRole, name="chat_role", values_callable=enum_values),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session = relationship("ChatSession", back_populates="messages")
