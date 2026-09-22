"""Stuart's final writer: grounded reports in, one manager-ready reply out."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.constants import SYNTHESIS_GEN_CONFIG, SYNTHESIS_MODEL
from agents.synthesis.prompt import SYNTHESIS_INSTRUCTION
from models.synthesis_output import SynthesisOutput


def _instruction(context: ReadonlyContext) -> str:
    parts = (context.user_content.parts if context.user_content else None) or []
    request = "\n".join(part.text for part in parts if getattr(part, "text", None))
    return f"{SYNTHESIS_INSTRUCTION}\n\nTURN INPUT\n{request}"


synthesis_agent = Agent(
    name="synthesis",
    model=SYNTHESIS_MODEL,
    description=(
        "Merges grounded specialist reports into one manager-facing briefing: "
        "Summary, Key Insights, Recommended Actions, and Artifacts."
    ),
    instruction=_instruction,
    tools=[],
    generate_content_config=SYNTHESIS_GEN_CONFIG,
    mode="single_turn",
    output_key="synthesis_result",
    output_schema=SynthesisOutput,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
