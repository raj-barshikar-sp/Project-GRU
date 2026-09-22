"""Asset grid and repurposing."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.content_generation.content_tools import (
    get_channel_specs,
    save_content_artifact,
)

from ..prompts import (
    CONTENT_ASSET_GRID_DESCRIPTION,
    CONTENT_ASSET_GRID_INSTRUCTION,
)

asset_grid_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="content_asset_grid",
    description=CONTENT_ASSET_GRID_DESCRIPTION,
    instruction=CONTENT_ASSET_GRID_INSTRUCTION,
    tools=[get_channel_specs, save_content_artifact],
    output_key="content_asset_grid",
)
