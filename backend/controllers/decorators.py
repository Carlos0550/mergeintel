"""Decorators for controllers: centralize try/except and ErrorResponse."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError

from backend.schemas.base import ErrorResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _integrity_error_to_response(exc: IntegrityError) -> ErrorResponse:
    """Map IntegrityError (e.g. unique violation) to ErrorResponse."""
    orig = getattr(exc, "orig", None)
    msg = str(orig) if orig is not None else str(exc)
    if "unique" in msg.lower() or "duplicate" in msg.lower() or "already exists" in msg.lower():
        if "email" in msg.lower() or "ix_user_email" in msg.lower():
            return ErrorResponse(
                success=False,
                message="El correo electrónico ya está registrado.",
                err=msg,
                err_code="DUPLICATE_EMAIL",
                status_code=409,
            )
        return ErrorResponse(
            success=False,
            message="Ya existe un registro con ese valor.",
            err=msg,
            err_code="DUPLICATE_KEY",
            status_code=409,
        )
    return ErrorResponse(
        success=False,
        message="Error de integridad en los datos.",
        err=msg,
        err_code="INTEGRITY_ERROR",
        status_code=400,
    )


def handle_controller_errors(
    default_message: str = "Ha ocurrido un error.",
    default_code: str = "ERROR",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decora un método async de controlador: captura excepciones y devuelve ErrorResponse.

    Uso:
        class MyController:
            @handle_controller_errors()
            async def my_action(self, data: RequestData) -> SucessWithData | ErrorResponse:
                ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except IntegrityError as e:
                logger.warning("Controller integrity error: %s", e, exc_info=True)
                return _integrity_error_to_response(e)
            except Exception as e:
                logger.exception("Unhandled error in controller %s", fn.__qualname__)
                return ErrorResponse(
                    success=False,
                    message=default_message,
                    err=str(e),
                    err_code=default_code,
                    status_code=500,
                )

        return wrapper

    return decorator
