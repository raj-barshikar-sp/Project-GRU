"""Campaign Strategy & Planning orchestrator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    CAMPAIGN_DESIGN_ORCHESTRATOR_DESCRIPTION,
    CAMPAIGN_DESIGN_ORCHESTRATOR_INSTRUCTION,
)
from .remote_agents import battlecard_agent
from .sub_agents import (
    brief_builder_agent,
    campaign_brief_deck,
    ideation_agent,
)

# The competitive battlecard specialist is now the remote A2A agent. Include it
# only when it resolved at import; without credentials it is None and we run
# with the remaining in-process specialists rather than crashing the app.
_SUB_AGENTS = [ideation_agent, brief_builder_agent, campaign_brief_deck]
if battlecard_agent is not None:
    _SUB_AGENTS.append(battlecard_agent)

campaign_design_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="campaign_design_orchestrator",
    description=CAMPAIGN_DESIGN_ORCHESTRATOR_DESCRIPTION,
    instruction=CAMPAIGN_DESIGN_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    sub_agents=_SUB_AGENTS,
)

root_agent = campaign_design_orchestrator
