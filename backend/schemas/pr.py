"""Pydantic schemas for PR analysis endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AnalyzePRRequest(BaseModel):
    pr_url: str | None = Field(default=None, description="Full GitHub pull request URL")
    owner: str | None = Field(default=None, description="GitHub repository owner")
    repo: str | None = Field(default=None, description="GitHub repository name")
    pr_number: int | None = Field(default=None, description="Pull request number")
    author_scopes: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Optional mapping of author login/email to expected path prefixes",
    )

    @model_validator(mode="after")
    def validate_pr_reference(self) -> AnalyzePRRequest:
        if self.pr_url:
            return self
        if self.owner and self.repo and self.pr_number:
            return self
        raise ValueError("Provide pr_url or owner, repo and pr_number.")


class ChecklistItemResponse(BaseModel):
    id: str
    title: str
    details: str | None
    severity: str
    completed: bool


class AuthorSummaryResponse(BaseModel):
    id: str
    github_login: str | None
    name: str | None
    email: str | None
    commit_count: int
    additions: int
    deletions: int
    inferred_scope: str | None
    scope_confidence: int | None


class FileSummaryResponse(BaseModel):
    id: str
    author_id: str | None
    commit_id: str | None
    path: str
    change_type: str
    additions: int
    deletions: int
    patch_truncated: bool
    is_schema_change: bool
    out_of_scope: bool
    scope_reason: str | None


class CommitSummaryResponse(BaseModel):
    id: str
    author_id: str | None
    sha: str
    message: str
    committed_at: str
    additions: int
    deletions: int


class PRAnalysisResponse(BaseModel):
    id: str
    repo_full_name: str
    pr_number: int
    pr_title: str
    pr_url: str
    base_branch: str
    head_branch: str
    status: str
    summary_text: str | None
    summary_payload: dict[str, Any] | None
    risk_score: int
    divergence_days: int
    error_message: str | None
    authors: list[AuthorSummaryResponse]
    commits: list[CommitSummaryResponse]
    files: list[FileSummaryResponse]
    checklist: list[ChecklistItemResponse]


class PRHistoryItem(BaseModel):
    id: str
    repo_full_name: str
    pr_number: int
    pr_title: str
    status: str
    risk_score: int
    created_at: str
