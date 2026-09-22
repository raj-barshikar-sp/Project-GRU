"""Salesforce: accounts, contacts, opportunities and campaign records."""

from __future__ import annotations

from typing import Protocol

from ..contracts import (
    Account,
    Campaign,
    CampaignResult,
    CampaignSpec,
    Contact,
    Opportunity,
    Region,
)
from ._fixtures import load


class SFDCConnector(Protocol):
    """The interface agents code against.

    `MockSFDC` reads sample files, a future `LiveSFDC` calls the real API.
    Because the agents only ever see this shape, swapping one for the other is
    a startup config change rather than a rewrite.
    """

    def list_accounts(self, region: Region | None = None) -> list[Account]: ...
    def list_contacts(self, account_ids: list[str] | None = None) -> list[Contact]: ...
    def list_opportunities(self, region: Region | None = None) -> list[Opportunity]: ...
    def list_campaigns(self, region: Region | None = None) -> list[Campaign]: ...
    def create_campaign(self, spec: CampaignSpec) -> CampaignResult: ...


class MockSFDC:
    def list_accounts(self, region: Region | None = None) -> list[Account]:
        accounts = [Account(**row) for row in load("accounts.json")]
        if region:
            accounts = [a for a in accounts if a.region == region]
        return accounts

    def list_contacts(self, account_ids: list[str] | None = None) -> list[Contact]:
        contacts = [Contact(**row) for row in load("contacts.json")]
        if account_ids is not None:
            wanted = set(account_ids)
            contacts = [c for c in contacts if c.account_id in wanted]
        return contacts

    def list_opportunities(self, region: Region | None = None) -> list[Opportunity]:
        opps = [Opportunity(**row) for row in load("opportunities.json")]
        if region:
            opps = [o for o in opps if o.owner_region == region]
        return opps

    def list_campaigns(self, region: Region | None = None) -> list[Campaign]:
        campaigns = [Campaign(**row) for row in load("campaigns.json")]
        if region:
            campaigns = [c for c in campaigns if c.region == region]
        return campaigns

    def create_campaign(self, spec: CampaignSpec) -> CampaignResult:
        """Mocked write. Returns a realistic result without touching anything.

        The id is derived from the campaign name rather than random, so the
        same request twice gives the same id and the demo is reproducible.
        """
        suffix = abs(hash(spec.name)) % 10_000
        return CampaignResult(
            campaign_id=f"701MOCK{suffix:04d}",
            name=spec.name,
            created=True,
            message=(
                f"MOCK: would create Salesforce campaign '{spec.name}' "
                f"({spec.type.value}, {spec.region.value}, "
                f"${spec.budget_usd:,} budget, {spec.start_date} to {spec.end_date})."
            ),
        )


# Convenience lookups used in several places.
def accounts_by_id(sfdc: SFDCConnector) -> dict[str, Account]:
    return {a.id: a for a in sfdc.list_accounts()}
