"""Rapid response campaign builder."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.brand.brand_tools import (
    get_executive_voices,
    get_trigger_events,
    save_brand_artifact,
)

from ..prompts import (
    BRAND_RAPID_RESPONSE_DESCRIPTION,
    BRAND_RAPID_RESPONSE_INSTRUCTION,
)

rapid_response_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="brand_rapid_response",
    description=BRAND_RAPID_RESPONSE_DESCRIPTION,
    instruction=BRAND_RAPID_RESPONSE_INSTRUCTION,
    tools=[get_trigger_events, get_executive_voices, save_brand_artifact],
    output_key="brand_rapid_response",
)
