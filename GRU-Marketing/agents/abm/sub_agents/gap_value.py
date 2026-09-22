"""Gap and value mapping."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.abm.abm_tools import get_gap_value_map

from ..prompts import (
    ABM_GAP_VALUE_DESCRIPTION,
    ABM_GAP_VALUE_INSTRUCTION,
)

gap_value_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_gap_value",
    description=ABM_GAP_VALUE_DESCRIPTION,
    instruction=ABM_GAP_VALUE_INSTRUCTION,
    tools=[get_gap_value_map],
    output_key="abm_gap_value",
)
