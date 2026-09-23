"""Campaign Strategy & Planning orchestrator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    campaign_design_orchestrator_description,
    campaign_design_orchestrator_instruction,
)
from .remote_agents import battlecard_agent
from .sub_agents import (
    brief_builder_agent,
    campaign_brief_deck,
    ideation_agent,
)

# The competitive battlecard specialist is the remote A2A agent. Include it only
# when it resolved at import; without credentials it is None and we run with the
# remaining in-process specialists rather than crashing the app.
_SPECIALISTS = [ideation_agent, brief_builder_agent, campaign_brief_deck]
if battlecard_agent is not None:
    _SPECIALISTS.append(battlecard_agent)

# Whether the battlecard is available shapes both the tool list and the prompt,
# so the orchestrator never advertises a specialist it cannot call.
_HAS_BATTLECARD = battlecard_agent is not None

campaign_design_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="campaign_design_orchestrator",
    description=campaign_design_orchestrator_description(_HAS_BATTLECARD),
    instruction=campaign_design_orchestrator_instruction(_HAS_BATTLECARD),
    planner=thinking_planner(),
    # AgentTool, not sub_agents: explicit calls return here, so ideation can
    # feed the brief and deck in one request instead of ending at the first
    # transfer.
    tools=[AgentTool(agent) for agent in _SPECIALISTS],
)

root_agent = campaign_design_orchestrator
