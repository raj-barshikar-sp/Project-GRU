"""Competitive positioning grounded in approved battlecards."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .base import BaseAgent, invoke_tool, value


class CompetitorPosition(BaseModel):
    """Approved strategy for one installed competitor."""

    competitor: str
    strategy: list[str]
    landmines: list[str]
    source: str | None = None


class CompetitivePositioningResult(BaseModel):
    """Positioning recommendations for detected competitors."""

    positions: list[CompetitorPosition]
    unmatched_technologies: list[str]
    summary: str


class CompetitivePositioningAgent(BaseAgent[CompetitivePositioningResult]):
    """Map installed competitors to battlecard strategy and landmines."""

    def __init__(self, battlecard_tool: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.battlecard_tool = battlecard_tool

    async def run(
        self,
        *,
        technographics: Any,
        battlecards: list[Any] | None = None,
        **_: Any,
    ) -> CompetitivePositioningResult:
        """Match technologies using normalized vendor/product names."""
        technologies = self._technology_names(technographics)
        cards = list(battlecards or [])
        if not cards and self.battlecard_tool is not None:
            fetched = await invoke_tool(
                self.battlecard_tool,
                (
                    "get_battlecard_for_competitors",
                    "get_battlecards",
                    "list_battlecards",
                    "search",
                    "get",
                ),
                competitors=technologies,
            )
            cards = list(value(fetched, "battlecards", "results", default=fetched or []))

        positions: list[CompetitorPosition] = []
        matched: set[str] = set()
        for technology in technologies:
            card = next((item for item in cards if self._matches(technology, item)), None)
            if card is None:
                continue
            matched.add(technology)
            positions.append(
                CompetitorPosition(
                    competitor=str(
                        value(card, "competitor", "vendor", "name", "product", default=technology)
                    ),
                    strategy=self._strings(
                        value(
                            card,
                            "strategies",
                            "strategy",
                            "positioning",
                            "talk_tracks",
                            "differentiators",
                            "proof_points",
                            default=[],
                        )
                    ),
                    landmines=self._strings(
                        value(card, "landmines", "traps", "warnings", "avoid", default=[])
                    ),
                    source=value(card, "source", "url", "document"),
                )
            )
        return CompetitivePositioningResult(
            positions=positions,
            unmatched_technologies=[item for item in technologies if item not in matched],
            summary=(
                f"Found approved positioning for {len(positions)} of "
                f"{len(technologies)} installed technologies."
            ),
        )

    @staticmethod
    def _technology_names(source: Any) -> list[str]:
        raw = value(
            source,
            "technologies",
            "installed_technology",
            "installed_technologies",
            "products",
            default=source or [],
        )
        if isinstance(raw, str):
            raw = [raw]
        return [
            str(value(item, "name", "product", "vendor", default=item)).strip()
            for item in raw
            if item
        ]

    @staticmethod
    def _matches(technology: str, card: Any) -> bool:
        left = "".join(character for character in technology.lower() if character.isalnum())
        aliases = value(card, "aliases", "products", default=[]) or []
        names = [
            value(card, "competitor", "vendor", "name", "product", default=""),
            *aliases,
        ]
        for name in names:
            right = "".join(character for character in str(name).lower() if character.isalnum())
            if right and (right in left or left in right):
                return True
        return False

    @staticmethod
    def _strings(raw: Any) -> list[str]:
        if isinstance(raw, str):
            return [raw]
        return [str(item) for item in (raw or []) if item]
