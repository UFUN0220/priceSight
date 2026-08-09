"""Small structured logging setup for replayable backend events."""

import json
import logging
from collections.abc import Mapping


class StructuredFormatter(logging.Formatter):
    """Serialize stable log fields without serializing arbitrary objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, Mapping):
            payload["context"] = dict(context)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure one deterministic root handler for local development."""

    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger without configuring global state."""

    return logging.getLogger(name)
