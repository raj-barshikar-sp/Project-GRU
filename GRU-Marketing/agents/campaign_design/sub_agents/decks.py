"""Campaign brief -> SailPoint PowerPoint.

Analyse (write the brief) then render. The shared analyse-then-render shape
lives in `agents/_shared/decks.py`; here we supply the brief analyst and the
slide writer. The order is fixed so a deck is never written from an invented
brief.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL

from agents._shared.decks import make_deck_pipeline
from ..prompts import (
    CAMPAIGN_BRIEF_DECK_ANALYST_INSTRUCTION,
    CAMPAIGN_BRIEF_DECK_DESCRIPTION,
    CAMPAIGN_BRIEF_DECK_WRITER_DESCRIPTION,
    CAMPAIGN_BRIEF_DECK_WRITER_INSTRUCTION,
    CAMPAIGN_BRIEF_BUILDER_DESCRIPTION,
)
from tools.campaign_design.campaign_design_tools import (
    get_campaign_brief_template,
    get_named_campaign,
    get_product_priorities,
    save_campaign_artifact,
)


def make_brief_agent(name: str) -> LlmAgent:
    return LlmAgent(
        model=DEFAULT_MODEL,
        name=name,
        description=CAMPAIGN_BRIEF_BUILDER_DESCRIPTION,
        instruction=CAMPAIGN_BRIEF_DECK_ANALYST_INSTRUCTION,
        tools=[
            get_named_campaign,
            get_campaign_brief_template,
            get_product_priorities,
            save_campaign_artifact,
        ],
        output_key="campaign_brief",
    )


campaign_brief_deck = make_deck_pipeline(
    name="campaign_brief_deck",
    description=CAMPAIGN_BRIEF_DECK_DESCRIPTION,
    analyst=make_brief_agent("campaign_brief_deck_analyst"),
    writer_name="campaign_brief_deck_writer",
    writer_description=CAMPAIGN_BRIEF_DECK_WRITER_DESCRIPTION,
    writer_instruction=CAMPAIGN_BRIEF_DECK_WRITER_INSTRUCTION,
    writer_output_key="campaign_brief_deck_summary",
    writer_tools=[
        get_named_campaign,
        get_campaign_brief_template,
        get_product_priorities,
        save_campaign_artifact,
    ],
)
