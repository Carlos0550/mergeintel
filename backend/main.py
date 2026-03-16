"""FastAPI application entry point."""

from __future__ import annotations

import os
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.logging_config import configure_logging


configure_logging(settings)

from backend.db.connection import close_engine, create_session_factory
from backend.routers.authentication import router as authentication_router
from backend.services.mail import build_mail_service


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources."""

    logger.info(
        "Application startup initiated",
        extra={"environment": settings.APP_ENV, "app_name": "MergeIntel API"},
    )

    try:
        build_mail_service(settings)
        await create_session_factory()
        logger.info(
            "Database session factory initialized",
            extra={"environment": settings.APP_ENV},
        )

        #limpiar consola
        if os.getenv("TERM"):
            os.system("cls" if os.name == "nt" else "clear")

        if settings.APP_ENV.lower() != "production":
            logger.info(
                "Development email mailbox available",
                extra={
                    "provider": "fastapi-mail",
                    "mail_ui_url": "http://localhost:8025",
                    "mail_server": settings.MAIL_SERVER,
                    "mail_port": settings.MAIL_PORT,
                },
            )
    except Exception:
        logger.exception(
            "Application startup failed",
            extra={"environment": settings.APP_ENV},
        )
        raise

    try:
        yield
    finally:
        logger.info(
            "Application shutdown initiated",
            extra={"environment": settings.APP_ENV},
        )
        await close_engine()
        logger.info(
            "Database engine closed",
            extra={"environment": settings.APP_ENV},
        )


app = FastAPI(
    title="MergeIntel API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authentication_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unhandled exceptions and return a safe 500 response."""

    logger.error(
        "Unhandled exception during request processing",
        extra={"path": request.url.path, "method": request.method},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the service health status."""

    logger.debug("Health endpoint requested", extra={"environment": settings.APP_ENV})
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
    }
