"""Anchor asset creator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.content_generation.content_tools import (
    get_anchor_asset_outline,
    get_brand_voice_guide,
    save_content_artifact,
)

from ..prompts import (
    CONTENT_ANCHOR_ASSET_DESCRIPTION,
    CONTENT_ANCHOR_ASSET_INSTRUCTION,
)

anchor_asset_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="content_anchor_asset",
    description=CONTENT_ANCHOR_ASSET_DESCRIPTION,
    instruction=CONTENT_ANCHOR_ASSET_INSTRUCTION,
    tools=[get_brand_voice_guide, get_anchor_asset_outline, save_content_artifact],
    output_key="content_anchor_asset",
)
