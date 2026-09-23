"""Content Generation orchestrator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    CONTENT_ORCHESTRATOR_DESCRIPTION,
    CONTENT_ORCHESTRATOR_INSTRUCTION,
)
from .sub_agents import (
    anchor_asset_agent,
    asset_grid_agent,
    campaign_variant_agent,
    localization_agent,
)

CONTENT_SPECIALISTS = (
    anchor_asset_agent,
    localization_agent,
    asset_grid_agent,
    campaign_variant_agent,
)

content_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="content_orchestrator",
    description=CONTENT_ORCHESTRATOR_DESCRIPTION,
    instruction=CONTENT_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    # AgentTool, not sub_agents: explicit calls return here, so one request can
    # chain anchor -> localization -> grid instead of ending at the first
    # transfer.
    tools=[AgentTool(agent) for agent in CONTENT_SPECIALISTS],
)

root_agent = content_orchestrator
