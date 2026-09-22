"""Checks on the remote BattleCard agent wiring.

Most of this runs without a model, a network or credentials: the agent card is
just JSON, and the campaign design tree can be inspected in memory. The one
live check that resolves the agent against the real Agent Registry skips itself
unless a real BATTLECARD_AGENT_ID is configured, so `uv run pytest` stays
offline and green.
"""

from __future__ import annotations

import os

import pytest
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

from agents.campaign_design import campaign_design_orchestrator
from agents.campaign_design.remote_agents import (
    agent_resource_name,
    battlecard_agent,
    build_battlecard_agent,
    load_agent_card,
)
from agents.campaign_design.remote_agents.battlecard_agent import REGISTRY_LOCATION
from ui.progress import status_for_author


def _has_real_agent_id() -> bool:
    agent_id = os.environ.get("BATTLECARD_AGENT_ID", "")
    return bool(agent_id) and not agent_id.startswith("<")


# --- the agent card, which is what ADK routes on --------------------------

def test_agent_card_carries_a_routing_grade_description():
    card = load_agent_card()

    assert card["name"] == "campaign_battlecard"
    # Routable specialists must say what they are NOT for; that is how near
    # neighbours (ABM plays, past performance) stay out of this lane.
    assert "NOT" in card["description"]
    assert len(card["description"]) > 40
    assert card["skills"], "the card should advertise at least one skill"


def test_resource_name_targets_us_west1_not_global():
    """The registry agent only exists in us-west1, never in global."""
    name = agent_resource_name()

    assert f"/locations/{REGISTRY_LOCATION}/" in name
    assert "/locations/global/" not in name


# --- the swap: remote battlecard replaces the local specialist ------------

def test_local_competitive_messaging_agent_is_gone():
    names = {a.name for a in campaign_design_orchestrator.sub_agents}

    assert "campaign_competitive_messaging" not in names
    # The remaining in-process specialists are always present.
    assert {
        "campaign_ideation",
        "campaign_brief_builder",
        "campaign_brief_deck",
    } <= names


def test_battlecard_agent_is_wired_when_it_resolves():
    """Without credentials the build returns None and the app runs without it."""
    if battlecard_agent is None:
        pytest.skip("remote agent unavailable (no credentials); nothing to wire")

    assert isinstance(battlecard_agent, RemoteA2aAgent)
    assert battlecard_agent.name == "campaign_battlecard"
    assert battlecard_agent in campaign_design_orchestrator.sub_agents


def test_progress_panel_has_copy_for_the_battlecard_author():
    assert status_for_author("campaign_battlecard") == (
        "Building the competitive battlecard…"
    )


# --- live: resolve against the real Agent Registry ------------------------

@pytest.mark.live
@pytest.mark.skipif(
    not _has_real_agent_id(),
    reason="set BATTLECARD_AGENT_ID and ADC to run the live registry check",
)
def test_build_returns_a_resolvable_remote_agent():
    agent = build_battlecard_agent()

    assert isinstance(agent, RemoteA2aAgent)
    assert agent.name == "campaign_battlecard"
    assert agent.description
