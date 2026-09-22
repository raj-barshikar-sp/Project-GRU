"""Salesforce account lookup tool."""

from __future__ import annotations

try:
    from ..config.settings import Settings
    from ..schemas.models import SalesforceAccount
    from .repository import JsonRepository
except ImportError:  # Support imports when ``henry_dsr_agent`` is the cwd.
    from config.settings import Settings
    from schemas.models import SalesforceAccount
    from tools.repository import JsonRepository


class SFDCTool:
    """Read-only account queries over a typed Salesforce fixture repository."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Initialize the account repository."""
        self._repository = JsonRepository(
            "salesforce_accounts.json", SalesforceAccount, settings=settings
        )

    def get_accounts_by_territory(self, territory: str) -> list[SalesforceAccount]:
        """Return accounts whose territory equals the requested value."""
        normalized = territory.strip().casefold()
        if not normalized:
            return []
        return [
            account
            for account in self._repository.all()
            if account.territory.casefold() == normalized
        ]

    def get_account_by_name(self, name: str) -> SalesforceAccount | None:
        """Return one exact account-name match, ignoring case and whitespace."""
        normalized = name.strip().casefold()
        if not normalized:
            return None
        return next(
            (
                account
                for account in self._repository.all()
                if account.name.casefold() == normalized
            ),
            None,
        )

    def find(self, query: str) -> list[SalesforceAccount]:
        """Find accounts by a case-insensitive name or domain fragment."""
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [
            account
            for account in self._repository.all()
            if normalized in account.name.casefold()
            or normalized in account.domain.casefold()
        ]
