"""Centralized logging configuration for the backend."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Any


_STANDARD_LOG_RECORD_ATTRS = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}


class JSONFormatter(logging.Formatter):
    """Serialize log records as JSON using only stdlib primitives."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = self._normalize_value(value)

        return json.dumps(payload, ensure_ascii=True)

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Convert custom logging extras into JSON-safe values."""

        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, dict):
            return {str(key): JSONFormatter._normalize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [JSONFormatter._normalize_value(item) for item in value]
        return str(value)


def configure_logging(app_settings: Any) -> None:
    """Configure application logging using dictConfig."""

    formatter_name = _resolve_formatter_name(app_settings.LOG_FORMAT)
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "backend.logging_config.JSONFormatter",
            },
            "text": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
        },
        "handlers": {},
        "root": {
            "level": app_settings.LOG_LEVEL,
            "handlers": [],
        },
        "loggers": {
            "uvicorn": {
                "level": app_settings.LOG_LEVEL,
                "handlers": [],
                "propagate": True,
            },
            "uvicorn.error": {
                "level": app_settings.LOG_LEVEL,
                "handlers": [],
                "propagate": True,
            },
            "uvicorn.access": {
                "level": app_settings.LOG_LEVEL,
                "handlers": [],
                "propagate": True,
            },
        },
    }

    if app_settings.LOG_ENABLE_STDOUT:
        config["handlers"]["stdout"] = {
            "class": "logging.StreamHandler",
            "level": app_settings.LOG_LEVEL,
            "formatter": formatter_name,
            "stream": "ext://sys.stdout",
        }
        config["root"]["handlers"].append("stdout")

    if app_settings.LOG_ENABLE_FILE:
        log_path = _ensure_log_file_path(app_settings.LOG_FILE_PATH)
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": app_settings.LOG_LEVEL,
            "formatter": formatter_name,
            "filename": str(log_path),
            "maxBytes": app_settings.LOG_FILE_MAX_BYTES,
            "backupCount": app_settings.LOG_FILE_BACKUP_COUNT,
            "encoding": "utf-8",
        }
        config["root"]["handlers"].append("file")

    if not config["root"]["handlers"]:
        raise ValueError("At least one logging handler must be enabled.")

    try:
        dictConfig(config)
    except Exception as exc:
        raise RuntimeError("Failed to configure application logging.") from exc


def _resolve_formatter_name(log_format: str) -> str:
    """Return the formatter name for the configured log format."""

    if log_format not in {"json", "text"}:
        raise ValueError(f"Unsupported log format: {log_format}")
    return log_format


def _ensure_log_file_path(path_value: str) -> Path:
    """Ensure the configured log file path is absolute and writable."""

    log_path = Path(path_value)
    if not log_path.is_absolute():
        raise ValueError("LOG_FILE_PATH must be an absolute path.")

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8"):
            pass
    except OSError as exc:
        raise RuntimeError(f"Log file path is not writable: {log_path}") from exc

    return log_path
