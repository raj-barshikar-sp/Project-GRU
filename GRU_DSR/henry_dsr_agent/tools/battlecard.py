"""Competitor battlecard lookup tool."""

from __future__ import annotations

from collections.abc import Iterable

try:
    from ..config.settings import Settings
    from ..schemas.models import Battlecard
    from .repository import JsonRepository
except ImportError:  # Support imports when ``henry_dsr_agent`` is the cwd.
    from config.settings import Settings
    from schemas.models import Battlecard
    from tools.repository import JsonRepository


class BattlecardTool:
    """Read-only access to normalized competitive intelligence."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Initialize the battlecard repository."""
        self._repository = JsonRepository(
            "battlecards.json", Battlecard, settings=settings
        )

    def get_battlecard_for_competitors(
        self, competitors: Iterable[str] | str
    ) -> list[Battlecard]:
        """Return known battlecards in requested order, skipping unknown names."""
        requested = [competitors] if isinstance(competitors, str) else list(competitors)
        normalized = [
            competitor.strip().casefold()
            for competitor in requested
            if isinstance(competitor, str) and competitor.strip()
        ]
        if not normalized:
            return []
        cards_by_name = {
            card.competitor.casefold(): card for card in self._repository.all()
        }
        unique_names = tuple(dict.fromkeys(normalized))
        return [cards_by_name[name] for name in unique_names if name in cards_by_name]
