"""The two deck builders.

Both are `SequentialAgent` chains with the same shape: analyse, then write the
slide plan and render it. That shared shape lives in `agents/_shared/decks.py`;
here we supply each deck's analyst, writer prompt and grounding tools. The order
is fixed in code because a deck written before the analysis exists would be
fiction.

Both decks run their own pipeline-health analyst as the first step and write to
the same `analysis_pipeline_health` state key. The writers read the analysis
back from that key. Within one turn the analyst still runs (a `SequentialAgent`
executes every step), so the reuse is across turns: once a pipeline analysis is
in session state, a later deck request can read it instead of recomputing.
"""

from __future__ import annotations

from agents._shared.decks import make_deck_pipeline
from tools.analysis.analysis_tools import (
    get_campaign_performance,
    get_pipeline_coverage,
    get_stage_distribution,
    get_stalled_deals,
)

from ..prompts import (
    ANALYSIS_DEMAND_COUNCIL_DECK_DESCRIPTION,
    ANALYSIS_DEMAND_COUNCIL_WRITER_DESCRIPTION,
    ANALYSIS_DEMAND_COUNCIL_WRITER_INSTRUCTION,
    ANALYSIS_PIPELINE_DECK_DESCRIPTION,
    ANALYSIS_PIPELINE_DECK_WRITER_DESCRIPTION,
    ANALYSIS_PIPELINE_DECK_WRITER_INSTRUCTION,
)
from .pipeline import make_pipeline_health_agent

pipeline_deck = make_deck_pipeline(
    name="analysis_pipeline_deck",
    description=ANALYSIS_PIPELINE_DECK_DESCRIPTION,
    analyst=make_pipeline_health_agent("analysis_pipeline_deck_analyst"),
    writer_name="analysis_pipeline_deck_writer",
    writer_description=ANALYSIS_PIPELINE_DECK_WRITER_DESCRIPTION,
    writer_instruction=ANALYSIS_PIPELINE_DECK_WRITER_INSTRUCTION,
    writer_output_key="analysis_pipeline_deck_summary",
    writer_tools=[get_pipeline_coverage, get_stage_distribution, get_stalled_deals],
)


demand_council_deck = make_deck_pipeline(
    name="analysis_demand_council_deck",
    description=ANALYSIS_DEMAND_COUNCIL_DECK_DESCRIPTION,
    analyst=make_pipeline_health_agent("analysis_demand_council_analyst"),
    writer_name="analysis_demand_council_writer",
    writer_description=ANALYSIS_DEMAND_COUNCIL_WRITER_DESCRIPTION,
    writer_instruction=ANALYSIS_DEMAND_COUNCIL_WRITER_INSTRUCTION,
    writer_output_key="analysis_demand_council_summary",
    writer_tools=[get_campaign_performance, get_pipeline_coverage, get_stalled_deals],
)
