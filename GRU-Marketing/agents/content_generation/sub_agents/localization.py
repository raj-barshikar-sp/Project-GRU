"""Localization and translation."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.content_generation.content_tools import (
    get_regional_glossary,
    save_content_artifact,
)

from ..prompts import (
    CONTENT_LOCALIZATION_DESCRIPTION,
    CONTENT_LOCALIZATION_INSTRUCTION,
)

localization_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="content_localization",
    description=CONTENT_LOCALIZATION_DESCRIPTION,
    instruction=CONTENT_LOCALIZATION_INSTRUCTION,
    tools=[get_regional_glossary, save_content_artifact],
    output_key="content_localization",
)
