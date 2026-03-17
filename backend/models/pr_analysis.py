"""PR analysis persistence models."""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel
from backend.models.user import enum_values


class AnalysisStatus(PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class ChecklistSeverity(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PRAnalysis(BaseModel):
    """Top-level persisted analysis of a GitHub pull request."""

    __tablename__ = "pr_analysis"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pr_title: Mapped[str] = mapped_column(String(500), nullable=False)
    pr_url: Mapped[str] = mapped_column(Text, nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status", values_callable=enum_values),
        nullable=False,
        default=AnalysisStatus.PENDING,
        server_default=AnalysisStatus.PENDING.value,
    )
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    divergence_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="pr_analyses")
    authors = relationship("PRAnalysisAuthor", back_populates="analysis", cascade="all, delete-orphan")
    commits = relationship("PRAnalysisCommit", back_populates="analysis", cascade="all, delete-orphan")
    files = relationship("PRAnalysisFile", back_populates="analysis", cascade="all, delete-orphan")
    checklist_items = relationship("PRChecklistItem", back_populates="analysis", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="analysis", cascade="all, delete-orphan")


class PRAnalysisAuthor(BaseModel):
    """Normalized author view for an analysis."""

    __tablename__ = "pr_analysis_author"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("pr_analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    github_login: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    inferred_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    analysis = relationship("PRAnalysis", back_populates="authors")
    commits = relationship("PRAnalysisCommit", back_populates="author")
    files = relationship("PRAnalysisFile", back_populates="author")


class PRAnalysisCommit(BaseModel):
    """Persisted commit metadata for a PR analysis."""

    __tablename__ = "pr_analysis_commit"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("pr_analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("pr_analysis_author.id", ondelete="SET NULL"), nullable=True, index=True)
    sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    committed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    analysis = relationship("PRAnalysis", back_populates="commits")
    author = relationship("PRAnalysisAuthor", back_populates="commits")
    files = relationship("PRAnalysisFile", back_populates="commit")


class PRAnalysisFile(BaseModel):
    """Normalized file-level change metadata for a PR analysis."""

    __tablename__ = "pr_analysis_file"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("pr_analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("pr_analysis_author.id", ondelete="SET NULL"), nullable=True, index=True)
    commit_id: Mapped[UUID | None] = mapped_column(ForeignKey("pr_analysis_commit.id", ondelete="SET NULL"), nullable=True, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    patch_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_schema_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    out_of_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    scope_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis = relationship("PRAnalysis", back_populates="files")
    author = relationship("PRAnalysisAuthor", back_populates="files")
    commit = relationship("PRAnalysisCommit", back_populates="files")


class PRChecklistItem(BaseModel):
    """Actionable checklist item generated for a PR analysis."""

    __tablename__ = "pr_checklist_item"

    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("pr_analysis.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[ChecklistSeverity] = mapped_column(
        Enum(ChecklistSeverity, name="checklist_severity", values_callable=enum_values),
        nullable=False,
        default=ChecklistSeverity.MEDIUM,
        server_default=ChecklistSeverity.MEDIUM.value,
    )
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    analysis = relationship("PRAnalysis", back_populates="checklist_items")
