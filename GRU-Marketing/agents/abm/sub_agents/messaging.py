"""Personalized messaging."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.abm.abm_tools import (
    get_persona_framework,
    get_regulatory_context,
)

from ..prompts import (
    ABM_MESSAGING_DESCRIPTION,
    ABM_MESSAGING_INSTRUCTION,
)

messaging_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_messaging",
    description=ABM_MESSAGING_DESCRIPTION,
    instruction=ABM_MESSAGING_INSTRUCTION,
    tools=[get_persona_framework, get_regulatory_context],
    output_key="abm_messaging",
)
