"""structlog configuration with secret-redaction processor."""

from __future__ import annotations

import logging
import re
import sys

import structlog

from app.config import settings

_REDACT_PATTERN = re.compile(r".*(_key|_secret|_password|_token)$", re.IGNORECASE)


def _redact_secrets(_logger, _method, event_dict):
    for key in list(event_dict.keys()):
        if _REDACT_PATTERN.match(key):
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
