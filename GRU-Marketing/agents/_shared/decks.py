"""Shared shape for deck pipelines: analyse, then render.

The analysis decks and the campaign brief deck are the same two-step chain: an
analyst writes grounded content to session state, then a writer turns it into a
.pptx via ``save_deck``. The order is fixed in code so a deck is never rendered
from content that does not exist yet. This factory is that shared shape, so a
team supplies only its analyst plus the writer's prompt and grounding tools;
``save_deck`` is always attached and the model choice stays in one place.
"""

from __future__ import annotations

from collections.abc import Sequence

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.analysis.deck_tools import save_deck


def make_deck_pipeline(
    *,
    name: str,
    description: str,
    analyst: BaseAgent,
    writer_name: str,
    writer_description: str,
    writer_instruction: str,
    writer_output_key: str,
    writer_tools: Sequence = (),
) -> SequentialAgent:
    """Build a fixed analyse-then-render chain.

    The writer always holds ``save_deck``; ``writer_tools`` adds whatever
    grounding tools the deck needs so figures are copied, never recomputed.
    """
    writer = LlmAgent(
        model=DEFAULT_MODEL,
        name=writer_name,
        description=writer_description,
        instruction=writer_instruction,
        tools=[save_deck, *writer_tools],
        output_key=writer_output_key,
    )
    return SequentialAgent(
        name=name,
        description=description,
        sub_agents=[analyst, writer],
    )
