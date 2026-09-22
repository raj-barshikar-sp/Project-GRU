"""ZoomInfo technographic and contact lookup tool."""

from __future__ import annotations

try:
    from ..config.settings import Settings
    from ..schemas.models import TechnographicIntel, normalize_domain
    from .repository import JsonRepository
except ImportError:  # Support imports when ``henry_dsr_agent`` is the cwd.
    from config.settings import Settings
    from schemas.models import TechnographicIntel, normalize_domain
    from tools.repository import JsonRepository


class ZoomInfoTool:
    """Read-only access to validated technology and contact intelligence."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Initialize the ZoomInfo intelligence repository."""
        self._repository = JsonRepository(
            "zoominfo_intelligence.json", TechnographicIntel, settings=settings
        )

    def get_tech_stack_and_contacts(
        self, domain: str
    ) -> TechnographicIntel | None:
        """Return intelligence for a domain, or ``None`` when unavailable."""
        try:
            normalized = normalize_domain(domain)
        except (TypeError, ValueError):
            return None
        return next(
            (
                record
                for record in self._repository.all()
                if record.domain == normalized
            ),
            None,
        )
