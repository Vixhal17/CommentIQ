import json
import logging
import sys
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Any, Optional

# Context variable for correlating logs to a specific comment/pipeline execution
current_comment_id: ContextVar[Optional[str]] = ContextVar("current_comment_id", default=None)

class JSONFormatter(logging.Formatter):
    """
    Format logs as single-line JSON objects with ISO 8601 timestamps
    and optional correlation IDs (comment_id).
    """
    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach correlation ID if set in current context or record
        cid = current_comment_id.get() or getattr(record, "comment_id", None)
        if cid:
            log_payload["comment_id"] = str(cid)

        # Attach any extra attributes
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload.update(record.extra_data)

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def get_logger(name: str = "yt_triage") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger

logger = get_logger()

