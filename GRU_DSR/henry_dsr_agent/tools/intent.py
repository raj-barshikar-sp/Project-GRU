"""6sense intent-signal lookup tool."""

from __future__ import annotations

try:
    from ..config.settings import Settings
    from ..schemas.models import IntentSignal, normalize_domain
    from .repository import JsonRepository
except ImportError:  # Support imports when ``henry_dsr_agent`` is the cwd.
    from config.settings import Settings
    from schemas.models import IntentSignal, normalize_domain
    from tools.repository import JsonRepository


class IntentTool:
    """Read-only domain lookups over validated 6sense mock signals."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Initialize the intent repository."""
        self._repository = JsonRepository(
            "intent_signals.json", IntentSignal, settings=settings
        )

    def get_intent_by_domain(self, domain: str) -> list[IntentSignal]:
        """Return matching signals ordered by descending score.

        Blank or malformed domains are treated as missing data and return an
        empty list, keeping lookup behavior safe for untrusted workflow input.
        """
        try:
            normalized = normalize_domain(domain)
        except (TypeError, ValueError):
            return []
        signals = [
            signal
            for signal in self._repository.all()
            if signal.domain == normalized
        ]
        return sorted(
            signals,
            key=lambda signal: (signal.score, signal.observed_at),
            reverse=True,
        )
