"""The two deck builders.

Both are `SequentialAgent` chains with the same shape: analyse, then write the
slide plan and render it. The order is fixed in code because a deck written
before the analysis exists would be fiction.

The two decks share their first step. `pipeline_health_agent` writes to
`analysis_pipeline_health`, and both writers read it from there, so asking for
the demand council deck after the pipeline deck does not repeat the work.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.analysis.analysis_tools import (
    get_campaign_performance,
    get_pipeline_coverage,
    get_stage_distribution,
    get_stalled_deals,
)
from tools.analysis.deck_tools import save_deck

from ..prompts import (
    ANALYSIS_DEMAND_COUNCIL_DECK_DESCRIPTION,
    ANALYSIS_DEMAND_COUNCIL_WRITER_DESCRIPTION,
    ANALYSIS_DEMAND_COUNCIL_WRITER_INSTRUCTION,
    ANALYSIS_PIPELINE_DECK_DESCRIPTION,
    ANALYSIS_PIPELINE_DECK_WRITER_DESCRIPTION,
    ANALYSIS_PIPELINE_DECK_WRITER_INSTRUCTION,
)
from .pipeline import make_pipeline_health_agent

pipeline_deck_writer = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_pipeline_deck_writer",
    description=ANALYSIS_PIPELINE_DECK_WRITER_DESCRIPTION,
    instruction=ANALYSIS_PIPELINE_DECK_WRITER_INSTRUCTION,
    tools=[save_deck, get_pipeline_coverage, get_stage_distribution,
           get_stalled_deals],
    output_key="analysis_pipeline_deck_summary",
)

pipeline_deck = SequentialAgent(
    name="analysis_pipeline_deck",
    description=ANALYSIS_PIPELINE_DECK_DESCRIPTION,
    sub_agents=[
        make_pipeline_health_agent("analysis_pipeline_deck_analyst"),
        pipeline_deck_writer,
    ],
)


demand_council_writer = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_demand_council_writer",
    description=ANALYSIS_DEMAND_COUNCIL_WRITER_DESCRIPTION,
    instruction=ANALYSIS_DEMAND_COUNCIL_WRITER_INSTRUCTION,
    tools=[save_deck, get_campaign_performance, get_pipeline_coverage,
           get_stalled_deals],
    output_key="analysis_demand_council_summary",
)

demand_council_deck = SequentialAgent(
    name="analysis_demand_council_deck",
    description=ANALYSIS_DEMAND_COUNCIL_DECK_DESCRIPTION,
    sub_agents=[
        make_pipeline_health_agent("analysis_demand_council_analyst"),
        demand_council_writer,
    ],
)
