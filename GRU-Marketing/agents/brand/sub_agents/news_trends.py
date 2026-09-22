"""News and trend analysis."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.brand.brand_tools import get_news_trends

from ..prompts import (
    BRAND_NEWS_TRENDS_DESCRIPTION,
    BRAND_NEWS_TRENDS_INSTRUCTION,
)

news_trends_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="brand_news_trends",
    description=BRAND_NEWS_TRENDS_DESCRIPTION,
    instruction=BRAND_NEWS_TRENDS_INSTRUCTION,
    tools=[get_news_trends],
    output_key="brand_news_trends",
)
