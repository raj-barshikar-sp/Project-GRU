"""Free-form writer; the specialist's material decides the reply shape."""

from __future__ import annotations

from google.adk.agents import Agent

from agents.constants import SYNTHESIS_GEN_CONFIG, SYNTHESIS_MODEL
from agents.synthesis.prompt import SYNTHESIS_INSTRUCTION

synthesis_agent = Agent(
    name="synthesis",
    model=SYNTHESIS_MODEL,
    description=(
        "Writes the AE-facing markdown answer after specialists query rows. "
        "Shape follows the specialist and the question — not a fixed template."
    ),
    instruction=SYNTHESIS_INSTRUCTION,
    tools=[],
    generate_content_config=SYNTHESIS_GEN_CONFIG,
    mode="single_turn",
    include_contents="none",
    output_key="synthesis_result",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
