"""Structured GitHub domain objects reused across services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GitHubUserProfile:
    provider_user_id: str
    provider_login: str
    email: str
    name: str
    access_token: str


@dataclass(slots=True)
class PRMetadata:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    author_login: str | None
    base_branch: str
    head_branch: str
    url: str
    state: str


@dataclass(slots=True)
class PRAuthor:
    key: str
    github_login: str | None
    name: str | None
    email: str | None
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    files: set[str] = field(default_factory=set)
    inferred_scope: str | None = None
    scope_confidence: int | None = None
    out_of_scope_paths: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PRCommit:
    sha: str
    message: str
    committed_at: str
    author_key: str
    github_login: str | None
    author_name: str | None
    author_email: str | None
    additions: int = 0
    deletions: int = 0


@dataclass(slots=True)
class PRFileChange:
    path: str
    change_type: str
    additions: int
    deletions: int
    patch: str | None
    author_key: str | None = None
    commit_sha: str | None = None
    patch_truncated: bool = False


@dataclass(slots=True)
class PRAnalysisInput:
    metadata: PRMetadata
    authors: dict[str, PRAuthor]
    commits: list[PRCommit]
    files: list[PRFileChange]
    divergence_days: int
    head_branch_missing: bool = False
