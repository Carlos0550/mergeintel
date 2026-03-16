"""API router package."""

from __future__ import annotations

from .authentication import router as authentication_router

__all__ = ["authentication_router"]