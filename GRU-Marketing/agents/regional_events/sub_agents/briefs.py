"""Account briefs, written in parallel.

Sequentially, briefing forty accounts means forty model round-trips and a demo
nobody waits for. The shape here is: fetch everything once in Python, split it
into groups, write the groups simultaneously, then merge.

Note where the parallelism actually is. The three writers do not each go and
fetch data; the preparation step already did that in one pass. They only write.
That keeps the fan-out cheap and means a slow data source cannot be hit three
times over.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.regional_events.events_tools import BRIEF_GROUPS, prepare_account_briefs

from ..prompts import (
    EVENTS_ACCOUNT_BRIEFS_DESCRIPTION,
    EVENTS_BRIEF_MERGER_DESCRIPTION,
    EVENTS_BRIEF_MERGER_INSTRUCTION,
    EVENTS_BRIEF_PREPARER_DESCRIPTION,
    EVENTS_BRIEF_PREPARER_INSTRUCTION,
    EVENTS_BRIEF_WRITERS_DESCRIPTION,
    events_brief_writer_description,
    events_brief_writer_instruction,
)

brief_preparer = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_brief_preparer",
    description=EVENTS_BRIEF_PREPARER_DESCRIPTION,
    instruction=EVENTS_BRIEF_PREPARER_INSTRUCTION,
    tools=[prepare_account_briefs],
    output_key="events_brief_prep",
)


def _make_writer(number: int) -> LlmAgent:
    """One of the parallel writers. Each sees only its own group's data."""
    return LlmAgent(
        model=DEFAULT_MODEL,
        name=f"events_brief_writer_{number}",
        description=events_brief_writer_description(number),
        instruction=events_brief_writer_instruction(number),
        output_key=f"events_brief_out_{number}",
    )


brief_writers = ParallelAgent(
    name="events_brief_writers",
    description=EVENTS_BRIEF_WRITERS_DESCRIPTION,
    sub_agents=[_make_writer(n) for n in range(1, BRIEF_GROUPS + 1)],
)

brief_merger = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_brief_merger",
    description=EVENTS_BRIEF_MERGER_DESCRIPTION,
    instruction=EVENTS_BRIEF_MERGER_INSTRUCTION,
    output_key="events_account_briefs",
)

account_brief_pipeline = SequentialAgent(
    name="events_account_briefs",
    description=EVENTS_ACCOUNT_BRIEFS_DESCRIPTION,
    sub_agents=[brief_preparer, brief_writers, brief_merger],
)
