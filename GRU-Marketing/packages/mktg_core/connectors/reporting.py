"""The three read-only reporting sources: Tableau, GA4 and Gainsight.

They are small enough to share a module. Each still has its own interface, so
splitting them out when a real integration arrives is trivial.
"""

from __future__ import annotations

from typing import Protocol

from ..contracts import Region
from ._fixtures import load


class TableauConnector(Protocol):
    """Where the pipeline targets live."""

    def coverage_target_multiple(self) -> float: ...
    def quarterly_pipeline_target(self, region: Region) -> int: ...
    def all_targets(self) -> dict[str, int]: ...


class MockTableau:
    def coverage_target_multiple(self) -> float:
        return float(load("targets.json")["coverage_target_multiple"])

    def quarterly_pipeline_target(self, region: Region) -> int:
        targets = load("targets.json")["quarterly_pipeline_target_usd"]
        return int(targets.get(region.value, 0))

    def all_targets(self) -> dict[str, int]:
        return {
            k: int(v)
            for k, v in load("targets.json")["quarterly_pipeline_target_usd"].items()
        }


class GA4Connector(Protocol):
    def sessions_for_campaign(self, campaign_id: str) -> int: ...


class MockGA4:
    """Web sessions derived from campaign clicks.

    Deliberately derived rather than stored: it keeps GA4 consistent with the
    campaign data instead of quietly contradicting it, which is exactly the
    kind of thing that makes a demo fall apart under questioning.
    """

    def sessions_for_campaign(self, campaign_id: str) -> int:
        for campaign in load("campaigns.json"):
            if campaign["id"] == campaign_id:
                # Roughly 82% of clicks become measurable sessions.
                return int(campaign["clicks"] * 0.82)
        return 0


class GainsightConnector(Protocol):
    def health_score(self, account_id: str) -> int | None: ...


class MockGainsight:
    def health_score(self, account_id: str) -> int | None:
        for account in load("accounts.json"):
            if account["id"] == account_id:
                return account.get("health_score")
        return None
