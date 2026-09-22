"""Brand Protection & Social Listening orchestrator."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    BRAND_ORCHESTRATOR_DESCRIPTION,
    BRAND_ORCHESTRATOR_INSTRUCTION,
)
from .sub_agents import (
    news_trends_agent,
    rapid_response_agent,
    sentiment_agent,
    sov_agent,
)

brand_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="brand_orchestrator",
    description=BRAND_ORCHESTRATOR_DESCRIPTION,
    instruction=BRAND_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    sub_agents=[
        sentiment_agent,
        sov_agent,
        news_trends_agent,
        rapid_response_agent,
    ],
)

root_agent = brand_orchestrator
