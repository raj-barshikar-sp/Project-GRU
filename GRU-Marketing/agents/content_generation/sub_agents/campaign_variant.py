"""Campaign-variant content packages."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.content_generation.content_tools import (
    get_brand_voice_guide,
    get_regional_glossary,
    save_content_artifact,
)

from ..prompts import (
    CONTENT_CAMPAIGN_VARIANT_DESCRIPTION,
    CONTENT_CAMPAIGN_VARIANT_INSTRUCTION,
)

campaign_variant_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="content_campaign_variant",
    description=CONTENT_CAMPAIGN_VARIANT_DESCRIPTION,
    instruction=CONTENT_CAMPAIGN_VARIANT_INSTRUCTION,
    tools=[get_brand_voice_guide, get_regional_glossary, save_content_artifact],
    output_key="content_campaign_variant",
)
