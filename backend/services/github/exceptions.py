"""GitHub integration exceptions."""

from __future__ import annotations

from backend.exceptions import AppError


class GitHubAPIError(AppError):
    """Base GitHub integration error."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when the GitHub API rate limit is exceeded."""


class RepoNotFoundError(GitHubAPIError):
    """Raised when a repository cannot be accessed."""


class PRNotFoundError(GitHubAPIError):
    """Raised when a pull request cannot be accessed."""


class BranchNotFoundError(GitHubAPIError):
    """Raised when a branch or ref does not exist in the repository."""
