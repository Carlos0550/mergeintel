"""Application-level exceptions with HTTP metadata."""

from __future__ import annotations


class AppError(RuntimeError):
    """Raised for expected business or integration errors."""

    def __init__(self, message: str, *, err_code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.err_code = err_code
        self.status_code = status_code
