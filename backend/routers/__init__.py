"""API router package."""

from __future__ import annotations

from .authentication import router as authentication_router
from .chat import router as chat_router
from .github import router as github_router
from .pr import router as pr_router

__all__ = ["authentication_router", "chat_router", "github_router", "pr_router"]
