"""Analysis orchestrator.

A router with six specialists and no tools of its own. It should never answer
an analytical question directly, because anything it says without calling a
specialist is by definition not grounded in the data.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    ANALYSIS_ORCHESTRATOR_DESCRIPTION,
    ANALYSIS_ORCHESTRATOR_INSTRUCTION,
)
from .sub_agents import (
    asset_influence_agent,
    campaign_performance_agent,
    demand_council_deck,
    improvement_recommender,
    pipeline_deck,
    pipeline_health_agent,
)

analysis_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_orchestrator",
    description=ANALYSIS_ORCHESTRATOR_DESCRIPTION,
    instruction=ANALYSIS_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    sub_agents=[
        campaign_performance_agent,
        improvement_recommender,
        pipeline_health_agent,
        asset_influence_agent,
        pipeline_deck,
        demand_council_deck,
    ],
)

root_agent = analysis_orchestrator
