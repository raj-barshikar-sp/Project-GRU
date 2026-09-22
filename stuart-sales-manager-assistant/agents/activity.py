"""Developer activity logger for routing and UI turns."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

LOGGER_NAME = "stuart.activity"
logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())

_CONFIGURED = False
_MAX_QUERY = 180


def _level() -> int:
    name = os.getenv("STUART_LOG_LEVEL", "INFO").strip().upper() or "INFO"
    return getattr(logging, name, logging.INFO)


def _log_path() -> Path:
    raw = os.getenv("STUART_LOG_FILE", "logs/stuart.log").strip() or "logs/stuart.log"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def configure_logging(*, force: bool = False) -> logging.Logger:
    """Attach console and file handlers once. Safe to call from UI and tests."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return logger
    if not force and "pytest" in sys.modules and not os.getenv("STUART_LOG_DURING_TESTS"):
        _CONFIGURED = True
        return logger

    logger.setLevel(_level())
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)
            handler.close()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if os.getenv("STUART_LOG_FILE", "logs/stuart.log").strip().lower() not in {
        "off",
        "none",
        "0",
    }:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _CONFIGURED = True
    logger.info("activity logger ready file=%s", _log_path())
    return logger


def preview(text: str, limit: int = _MAX_QUERY) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def log_activity(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Log one developer-facing activity line with compact JSON fields."""
    payload = {
        key: value
        for key, value in fields.items()
        if value not in (None, "", [], {}, ())
    }
    if payload:
        try:
            extras = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
        except TypeError:
            extras = str(payload)
        logger.log(level, "%s %s", event, extras)
    else:
        logger.log(level, "%s", event)
