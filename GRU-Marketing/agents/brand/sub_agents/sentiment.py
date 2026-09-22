"""Social sentiment and response drafting."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.brand.brand_tools import (
    get_brand_response_playbook,
    get_social_sentiment,
)

from ..prompts import (
    BRAND_SOCIAL_SENTIMENT_DESCRIPTION,
    BRAND_SOCIAL_SENTIMENT_INSTRUCTION,
)

sentiment_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="brand_social_sentiment",
    description=BRAND_SOCIAL_SENTIMENT_DESCRIPTION,
    instruction=BRAND_SOCIAL_SENTIMENT_INSTRUCTION,
    tools=[get_social_sentiment, get_brand_response_playbook],
    output_key="brand_social_sentiment",
)
