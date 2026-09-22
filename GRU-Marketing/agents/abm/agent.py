"""ABM & Account Intelligence orchestrator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import ABM_ORCHESTRATOR_DESCRIPTION, ABM_ORCHESTRATOR_INSTRUCTION
from .sub_agents import (
    account_intel_agent,
    account_selection_agent,
    gap_value_agent,
    messaging_agent,
    multichannel_package,
)

ABM_SPECIALISTS = (
    account_selection_agent,
    account_intel_agent,
    gap_value_agent,
    messaging_agent,
    multichannel_package,
)

abm_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_orchestrator",
    description=ABM_ORCHESTRATOR_DESCRIPTION,
    instruction=ABM_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    # Explicit calls return here, allowing one request to run several ABM
    # specialists instead of ending at the first transfer.
    tools=[AgentTool(agent) for agent in ABM_SPECIALISTS],
)

root_agent = abm_orchestrator
