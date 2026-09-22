"""Pipeline health and content influence.

`pipeline_health` writes its answer to session state, and both deck builders
read it from there. That is the main reason these are in-process sub-agents
rather than separate services: the deck chain gets the analysis for free
instead of recomputing or re-serialising it.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools._shared.profile_tools import get_current_user
from tools.analysis.analysis_tools import (
    get_asset_influence,
    get_pipeline_coverage,
    get_stage_distribution,
    get_stage_movement,
    get_stalled_deals,
)

from ..prompts import (
    ANALYSIS_ASSET_INFLUENCE_DESCRIPTION,
    ANALYSIS_ASSET_INFLUENCE_INSTRUCTION,
    ANALYSIS_PIPELINE_HEALTH_DESCRIPTION,
    ANALYSIS_PIPELINE_HEALTH_INSTRUCTION,
)


def make_pipeline_health_agent(name: str = "analysis_pipeline_health") -> LlmAgent:
    """A fresh pipeline analyst.

    This is a factory rather than a shared instance because ADK gives every
    agent exactly one parent, and this analysis is needed in three places: on
    its own, and as the first step of each deck chain. The name differs per
    instance so agent lookup stays unambiguous, but they all write to the same
    `analysis_pipeline_health` state key, which is what lets the deck writers
    read the analysis instead of redoing it.
    """
    return LlmAgent(
        model=DEFAULT_MODEL,
        name=name,
        description=ANALYSIS_PIPELINE_HEALTH_DESCRIPTION,
        instruction=ANALYSIS_PIPELINE_HEALTH_INSTRUCTION,
        tools=[
            get_pipeline_coverage,
            get_stage_distribution,
            get_stalled_deals,
            get_stage_movement,
            get_current_user,
        ],
        output_key="analysis_pipeline_health",
    )


pipeline_health_agent = make_pipeline_health_agent()


asset_influence_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_asset_influence",
    description=ANALYSIS_ASSET_INFLUENCE_DESCRIPTION,
    instruction=ANALYSIS_ASSET_INFLUENCE_INSTRUCTION,
    tools=[get_asset_influence],
    output_key="analysis_asset_influence",
)
