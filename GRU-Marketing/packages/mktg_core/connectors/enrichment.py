"""Account enrichment: ZoomInfo / BuiltWith stand-in."""

from __future__ import annotations

from typing import Protocol

from ..contracts import CompanyFacts, Technographic
from ._fixtures import load


class EnrichmentConnector(Protocol):
    def list_technographics(
        self, account_ids: list[str] | None = None
    ) -> list[Technographic]: ...
    def get_company_facts(self, account_id: str) -> CompanyFacts | None: ...
    def list_company_facts(
        self, account_ids: list[str] | None = None
    ) -> list[CompanyFacts]: ...


class MockEnrichment:
    def list_technographics(
        self, account_ids: list[str] | None = None
    ) -> list[Technographic]:
        rows = [Technographic(**r) for r in load("technographics.json")]
        if account_ids is not None:
            wanted = set(account_ids)
            rows = [r for r in rows if r.account_id in wanted]
        return rows

    def get_company_facts(self, account_id: str) -> CompanyFacts | None:
        for row in load("company_facts.json"):
            if row["account_id"] == account_id:
                return CompanyFacts(
                    account_id=row["account_id"],
                    revenue_growth_pct=row.get("revenue_growth_pct"),
                    recent_leadership_change=row.get(
                        "leadership_change", row.get("recent_leadership_change", "")
                    ),
                    recent_news=row.get("recent_news", ""),
                    strategic_priorities=row.get(
                        "priorities", row.get("strategic_priorities", [])
                    ),
                    compliance_drivers=row.get("compliance_drivers", []),
                )
        return None

    def list_company_facts(
        self, account_ids: list[str] | None = None
    ) -> list[CompanyFacts]:
        facts = [
            self.get_company_facts(row["account_id"])
            for row in load("company_facts.json")
        ]
        facts = [f for f in facts if f is not None]
        if account_ids is not None:
            wanted = set(account_ids)
            facts = [f for f in facts if f.account_id in wanted]
        return facts
