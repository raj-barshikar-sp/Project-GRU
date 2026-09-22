"""Coverage for the complete seller-facing DSR ask catalog."""

import pytest
from fastapi.testclient import TestClient
from henry_dsr_agent.agents import DSRAskAction
from henry_dsr_agent.api.server import create_app
from henry_dsr_agent.orchestrator import HenryOrchestrator


def test_catalog_contains_every_requested_dsr_action() -> None:
    assert len(DSRAskAction) == 26
    assert {
        DSRAskAction.COLD_CALL_COACHING,
        DSRAskAction.TERRITORY_WHITESPACE,
        DSRAskAction.ACCOUNT_360_HEALTHCHECK,
        DSRAskAction.DIGITAL_SALES_ROOM,
        DSRAskAction.QUOTE_DISCOUNT_CHECKER,
        DSRAskAction.POST_SALES_HANDOFF,
        DSRAskAction.COMMISSION_PLANS,
    }.issubset(set(DSRAskAction))


@pytest.mark.asyncio
async def test_every_catalog_action_executes_with_local_data() -> None:
    orchestrator = HenryOrchestrator()
    for action in DSRAskAction:
        result = await orchestrator.ask(
            {
                "action": action.value,
                "message": action.value.replace("_", " "),
                "account_id": "001APEXFIN000001",
                "context": {},
            }
        )
        ask = result.data["ask"]
        assert ask["action"] == action.value
        assert ask["markdown"]
        assert ask["needs_account_selection"] is False


@pytest.mark.asyncio
async def test_account_scoped_ask_requests_account_selection() -> None:
    result = await HenryOrchestrator().ask(
        {"action": "account_plan", "message": "Build an account plan", "context": {}}
    )
    assert result.data["ask"]["needs_account_selection"] is True
    assert "select" in result.markdown.lower()


def test_ask_api_executes_explicit_catalog_action() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/ask",
            json={
                "action": "competitive_positioning_deck",
                "message": "Build the battlecard",
                "account_id": "001APEXFIN000001",
            },
        )
    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["data"]["ask"]["action"] == "competitive_positioning_deck"
