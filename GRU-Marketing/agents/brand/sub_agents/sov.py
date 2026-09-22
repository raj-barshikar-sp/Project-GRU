"""Share of voice tracking."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.brand.brand_tools import get_share_of_voice

from ..prompts import (
    BRAND_SHARE_OF_VOICE_DESCRIPTION,
    BRAND_SHARE_OF_VOICE_INSTRUCTION,
)

sov_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="brand_share_of_voice",
    description=BRAND_SHARE_OF_VOICE_DESCRIPTION,
    instruction=BRAND_SHARE_OF_VOICE_INSTRUCTION,
    tools=[get_share_of_voice],
    output_key="brand_share_of_voice",
)
