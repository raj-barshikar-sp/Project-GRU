"""Campaign brief builder."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.campaign_design.campaign_design_tools import (
    get_campaign_brief_template,
    save_campaign_artifact,
)

from ..prompts import (
    CAMPAIGN_BRIEF_BUILDER_DESCRIPTION,
    CAMPAIGN_BRIEF_BUILDER_INSTRUCTION,
)

brief_builder_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="campaign_brief_builder",
    description=CAMPAIGN_BRIEF_BUILDER_DESCRIPTION,
    instruction=CAMPAIGN_BRIEF_BUILDER_INSTRUCTION,
    tools=[get_campaign_brief_template, save_campaign_artifact],
    output_key="campaign_brief",
)
