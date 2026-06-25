"""Structured logging helpers with request correlation IDs."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TextIO

CORRELATION_ID_FIELD = "correlation_id"
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")


def new_correlation_id() -> str:
    """Create a fresh request correlation ID."""

    return str(uuid.uuid4())


def get_correlation_id() -> str:
    """Return the active correlation ID for the current context."""

    return _correlation_id.get()


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation ID for all logs emitted in this context."""

    resolved = correlation_id or new_correlation_id()
    token = _correlation_id.set(resolved)
    try:
        yield resolved
    finally:
        _correlation_id.reset(token)


class JsonLogFormatter(logging.Formatter):
    """Format log records as compact JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            CORRELATION_ID_FIELD: getattr(record, CORRELATION_ID_FIELD, get_correlation_id()),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in _standard_log_record_keys():
                continue
            if key == CORRELATION_ID_FIELD:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    force: bool = False,
) -> None:
    """Configure root logging for JSON output."""

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonLogFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=force)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured INFO event with the active correlation ID."""

    logger.info(
        event,
        extra={CORRELATION_ID_FIELD: get_correlation_id(), "event": event, **fields},
    )


def _standard_log_record_keys() -> set[str]:
    return {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }
