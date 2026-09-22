"""Connector selection.

One env var decides whether the system runs on sample files or real APIs:

    MKTG_DATA_SOURCE=mock   (default)
    MKTG_DATA_SOURCE=live   (not implemented yet, fails loudly)

Agents and tools always call `get_connectors()`. They never import a specific
implementation, which is what keeps the mock-to-live swap a config change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .channels import ChannelsConnector, MockChannels
from .enrichment import EnrichmentConnector, MockEnrichment
from .events import EventsConnector, MockEvents
from .kb import KBConnector, MockKB
from .market_intel import MarketIntelConnector, MockMarketIntel
from .marketo import MarketoConnector, MockMarketo
from .reporting import (
    GA4Connector,
    GainsightConnector,
    MockGA4,
    MockGainsight,
    MockTableau,
    TableauConnector,
)
from .sfdc import MockSFDC, SFDCConnector, accounts_by_id
from .sixsense import MockSixSense, SixSenseConnector


@dataclass(frozen=True)
class Connectors:
    """Every source system, handed to tools as one object."""

    sfdc: SFDCConnector
    sixsense: SixSenseConnector
    marketo: MarketoConnector
    tableau: TableauConnector
    ga4: GA4Connector
    gainsight: GainsightConnector
    events: EventsConnector
    kb: KBConnector
    enrichment: EnrichmentConnector
    market_intel: MarketIntelConnector
    channels: ChannelsConnector


_MOCK = Connectors(
    sfdc=MockSFDC(),
    sixsense=MockSixSense(),
    marketo=MockMarketo(),
    tableau=MockTableau(),
    ga4=MockGA4(),
    gainsight=MockGainsight(),
    events=MockEvents(),
    kb=MockKB(),
    enrichment=MockEnrichment(),
    market_intel=MockMarketIntel(),
    channels=MockChannels(),
)


def get_connectors() -> Connectors:
    source = os.environ.get("MKTG_DATA_SOURCE", "mock").lower()
    if source == "mock":
        return _MOCK
    if source == "live":
        raise NotImplementedError(
            "Live connectors are not built yet. This is the seam where real "
            "Salesforce/6sense/Marketo clients get wired in. "
            "Unset MKTG_DATA_SOURCE to use the sample dataset."
        )
    raise ValueError(f"Unknown MKTG_DATA_SOURCE={source!r}. Use 'mock' or 'live'.")


__all__ = [
    "Connectors",
    "get_connectors",
    "accounts_by_id",
]
