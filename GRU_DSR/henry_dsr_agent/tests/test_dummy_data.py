"""Integrity checks for the linked local demonstration database."""

import json
from pathlib import Path
from typing import Any

from henry_dsr_agent.schemas import (
    Battlecard,
    IntentSignal,
    SalesforceAccount,
    TechnographicIntel,
)

DATA_DIR = Path(__file__).parents[1] / "data"


def _records(filename: str) -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def test_expanded_database_is_linked_and_schema_valid() -> None:
    accounts = [
        SalesforceAccount.model_validate(item)
        for item in _records("salesforce_accounts.json")
    ]
    signals = [IntentSignal.model_validate(item) for item in _records("intent_signals.json")]
    intel = [
        TechnographicIntel.model_validate(item)
        for item in _records("zoominfo_intelligence.json")
    ]
    cards = [Battlecard.model_validate(item) for item in _records("battlecards.json")]

    assert len(accounts) >= 15
    assert len(cards) >= 10
    assert {item.domain for item in accounts} == {item.domain for item in signals}
    assert {item.domain for item in accounts} == {item.domain for item in intel}
    assert {"US-WEST", "US-EAST", "US-CENTRAL", "EMEA", "APAC"} <= {
        item.territory for item in accounts
    }


def test_mock_fixture_mirrors_match_canonical_sources() -> None:
    pairs = (
        ("salesforce_accounts.json", "mock_sfdc_accounts.json"),
        ("intent_signals.json", "mock_6sense_intent.json"),
        ("zoominfo_intelligence.json", "mock_zoominfo_tech.json"),
        ("battlecards.json", "mock_battlecards.json"),
    )
    for canonical, mirror in pairs:
        assert _records(canonical) == _records(mirror)
