"""Helpers for working with the application timezone."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from backend.config import settings


@lru_cache(maxsize=1)
def get_app_timezone() -> ZoneInfo:
    """Return the configured application timezone."""

    return ZoneInfo(settings.APP_TIMEZONE)


def now_in_app_timezone() -> datetime:
    """Return the current datetime using the configured application timezone."""

    return datetime.now(tz=get_app_timezone())
