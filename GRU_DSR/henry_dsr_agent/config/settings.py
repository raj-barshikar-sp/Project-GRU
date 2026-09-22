"""Typed runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Application settings with dependency-free environment loading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "data"
    )
    mock_latency_ms: int = Field(default=75, ge=0, le=30_000)
    mock_latency_jitter_ms: int = Field(default=25, ge=0, le=10_000)

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, value: object) -> Path:
        """Normalize user-relative and environment-variable paths."""
        if not isinstance(value, (str, Path)):
            raise TypeError("data_dir must be a string or pathlib.Path")
        return Path(os.path.expandvars(str(value))).expanduser().resolve()

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from ``HENRY_*`` environment variables."""
        values: dict[str, object] = {}
        if data_dir := os.getenv("HENRY_DATA_DIR"):
            values["data_dir"] = data_dir
        for field_name, environment_name in (
            ("mock_latency_ms", "HENRY_MOCK_LATENCY_MS"),
            ("mock_latency_jitter_ms", "HENRY_MOCK_LATENCY_JITTER_MS"),
        ):
            raw = os.getenv(environment_name)
            if raw is not None:
                try:
                    values[field_name] = int(raw)
                except ValueError as exc:
                    raise ValueError(f"{environment_name} must be an integer") from exc
        return cls(**values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide immutable settings instance."""
    return Settings.from_env()
