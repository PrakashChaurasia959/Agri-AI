"""Structured logging that never leaks secrets.

The formatter redacts a small deny-list of sensitive keys (passwords, tokens,
database URIs, API keys) so that accidental ``logger.info("... %s", uri)``
calls cannot leak credentials into log aggregators.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|mongodb_uri|database_url)",
    re.IGNORECASE,
)

_REDACTED = "***redacted***"


def _redact(value: Any, key: str | None = None) -> Any:
    if key and _SENSITIVE_KEY_PATTERN.search(key):
        return _REDACTED
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class SecretRedactingFilter(logging.Filter):
    """Redacts sensitive keys from structured log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, dict):
            record.msg = _redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = _redact(record.args)
            else:
                record.args = tuple(_redact(arg) for arg in record.args)
        return True


class JsonFormatter(logging.Formatter):
    """Compact single-line JSON formatter for structured log shipping."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure root logging with redaction enabled."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SecretRedactingFilter())

    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root.addHandler(handler)

    # Third-party libraries are noisy at INFO level.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
