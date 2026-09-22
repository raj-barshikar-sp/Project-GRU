"""Campaign ideation."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.campaign_design.campaign_design_tools import (
    get_campaign_performance_signals,
    get_pipeline_gaps_for_ideation,
    get_product_priorities,
)

from ..prompts import (
    CAMPAIGN_IDEATION_DESCRIPTION,
    CAMPAIGN_IDEATION_INSTRUCTION,
)

ideation_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="campaign_ideation",
    description=CAMPAIGN_IDEATION_DESCRIPTION,
    instruction=CAMPAIGN_IDEATION_INSTRUCTION,
    tools=[
        get_pipeline_gaps_for_ideation,
        get_campaign_performance_signals,
        get_product_priorities,
    ],
    output_key="campaign_ideation",
)
