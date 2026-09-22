"""Reusable latency-enabled JSON repository infrastructure."""

from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

try:
    from ..config.settings import Settings, get_settings
except ImportError:  # Support imports when ``henry_dsr_agent`` is the cwd.
    from config.settings import Settings, get_settings

ModelT = TypeVar("ModelT", bound=BaseModel)


class RepositoryError(RuntimeError):
    """Raised when a repository source is unreadable or invalid."""


class JsonRepository(Generic[ModelT]):
    """Thread-safe typed repository backed by a JSON array."""

    def __init__(
        self,
        filename: str,
        model_type: type[ModelT],
        *,
        settings: Settings | None = None,
    ) -> None:
        """Configure a repository without performing file I/O."""
        if not filename.endswith(".json") or Path(filename).name != filename:
            raise ValueError("filename must be a simple .json filename")
        self._settings = settings or get_settings()
        self._path = self._settings.data_dir / filename
        self._adapter = TypeAdapter(list[model_type])
        self._records: tuple[ModelT, ...] | None = None
        self._lock = threading.RLock()

    def _simulate_latency(self) -> None:
        """Pause to emulate a remote enterprise API request."""
        base = self._settings.mock_latency_ms
        jitter = self._settings.mock_latency_jitter_ms
        duration_ms = base + (random.uniform(0, jitter) if jitter else 0)
        if duration_ms:
            time.sleep(duration_ms / 1_000)

    def _load(self) -> tuple[ModelT, ...]:
        """Load and validate records once, safely across concurrent callers."""
        if self._records is not None:
            return self._records
        with self._lock:
            if self._records is not None:
                return self._records
            try:
                with self._path.open("r", encoding="utf-8") as source:
                    payload = json.load(source)
                records = self._adapter.validate_python(payload)
            except FileNotFoundError as exc:
                raise RepositoryError(f"Data source not found: {self._path}") from exc
            except json.JSONDecodeError as exc:
                raise RepositoryError(
                    f"Data source contains invalid JSON: {self._path}"
                ) from exc
            except ValidationError as exc:
                raise RepositoryError(
                    f"Data source failed schema validation: {self._path}"
                ) from exc
            except OSError as exc:
                raise RepositoryError(f"Unable to read data source: {self._path}") from exc
            self._records = tuple(records)
            return self._records

    def all(self) -> tuple[ModelT, ...]:
        """Return all validated records after applying simulated latency."""
        self._simulate_latency()
        return self._load()

    def clear_cache(self) -> None:
        """Clear loaded records so the next request rereads the source."""
        with self._lock:
            self._records = None
