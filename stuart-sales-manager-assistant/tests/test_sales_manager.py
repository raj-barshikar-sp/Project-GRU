"""Current snapshots and no-tool specialist contracts."""

from __future__ import annotations

import importlib
import json

import pytest

from agents.data_context import SOURCES_BY_AGENT, source_context
from agents.new_data_store import (
    data_ready,
    normalized_calendar_events,
    normalized_deal_intelligence,
    normalized_email_threads,
    normalized_opportunities,
    sales_users,
    workday,
)
from agents.orchestrator.prompt import TASK_AGENT_IDS


@pytest.mark.parametrize("agent_id", TASK_AGENT_IDS)
def test_every_specialist_has_profile_and_no_tools(agent_id: str) -> None:
    module = importlib.import_module(f"agents.{agent_id}.agent")
    agent = getattr(module, f"{agent_id}_agent")
    instruction = agent.instruction(None)
    assert agent.name == agent_id
    assert agent.tools == []
    assert agent.output_schema.__name__ == "SpecialistReport"
    assert all(
        heading in instruction
        for heading in ("ROLE", "PERSONA", "OBJECTIVE", "INSTRUCTIONS", "GUARDRAILS")
    )
    assert "<data_source" in instruction


@pytest.mark.parametrize("agent_id", TASK_AGENT_IDS)
def test_each_specialist_receives_valid_json(agent_id: str) -> None:
    context = source_context(agent_id)
    assert context
    for name in SOURCES_BY_AGENT[agent_id]:
        marker = f'<data_source name="{name}">\n'
        payload = context.split(marker, 1)[1].split("\n</data_source>", 1)[0]
        assert json.loads(payload)


def test_snapshot_links_are_complete() -> None:
    assert data_ready()
    users = {row["Id"] for row in sales_users()}
    employees = {row["sfdc_user_id"] for row in workday()["employees"]}
    opportunities = normalized_opportunities()
    opportunity_ids = {row["Id"] for row in opportunities}
    assert len(opportunities) == 19
    assert users <= employees
    assert all(row["OwnerId"] in users for row in opportunities)
    assert all(
        row["opportunity_id"] in opportunity_ids
        for row in (
            normalized_calendar_events()
            + normalized_email_threads()
            + normalized_deal_intelligence()
        )
    )


def test_salesforce_context_includes_exact_aggregate_summary() -> None:
    context = source_context("crm_intelligence_specialist")
    assert '"deal_count": 19' in context
    assert '"acv_total": 6650000' in context
    assert '"deal_count": 11' in context
    assert '"acv_total": 3320000' in context
