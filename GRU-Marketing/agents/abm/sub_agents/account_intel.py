"""Account intel and research."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.abm.abm_tools import get_account_intel_brief

from ..prompts import (
    ABM_ACCOUNT_INTEL_DESCRIPTION,
    ABM_ACCOUNT_INTEL_INSTRUCTION,
)

account_intel_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_account_intel",
    description=ABM_ACCOUNT_INTEL_DESCRIPTION,
    instruction=ABM_ACCOUNT_INTEL_INSTRUCTION,
    tools=[get_account_intel_brief],
    output_key="abm_account_intel",
)
