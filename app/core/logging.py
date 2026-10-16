"""Structured JSON logging with sensitive data redaction."""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict

# Regex patterns to redact sensitive tokens/keys
SENSITIVE_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9_\-]{8,})"),
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"(gsk_[a-zA-Z0-9_\-]{8,})"),
    re.compile(r"('api[-_]?key'\s*:\s*')[^']+(\')", re.IGNORECASE),
    re.compile(r'("api[-_]?key"\s*:\s*")[^"]+(")', re.IGNORECASE),
]


def redact_sensitive_string(text: str) -> str:
    """Redacts known API key patterns from text."""
    if not isinstance(text, str):
        return text
    result = text
    for pattern in SENSITIVE_PATTERNS:
        result = pattern.sub(r"[REDACTED_SECRET]", result)
    return result


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_string(record.getMessage()),
        }

        # Include custom attributes attached to LogRecord
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            }:
                if isinstance(value, str):
                    log_payload[key] = redact_sensitive_string(value)
                else:
                    log_payload[key] = value

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configures application-wide structured JSON logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(stream_handler)

    # Suppress verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger("llm_gateway")


logger = setup_logging()
