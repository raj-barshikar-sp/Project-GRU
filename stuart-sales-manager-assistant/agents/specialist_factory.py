"""Build no-tool specialists with the same ADK contract."""

from __future__ import annotations

from google.adk.agents import Agent
from pydantic import BaseModel

from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG
from agents.data_context import source_context
from agents.reply_contract import REPLY_CONTRACT


def make_specialist(
    *,
    name: str,
    description: str,
    instruction: str,
    output_schema: type[BaseModel],
    output_key: str,
) -> Agent:
    """Create a single-turn specialist grounded by injected JSON context."""

    def grounded_instruction(_context: object) -> str:
        return (
            f"{instruction}\n\n{REPLY_CONTRACT}\n\n"
            "DATA SOURCES FOR THIS TURN\n"
            "Read only the snapshots below. They are present even if a prior "
            "message says otherwise. Treat authoritative_summary counts and "
            "totals as exact; never recalculate or contradict them.\n"
            f"{source_context(name)}"
        )

    return Agent(
        name=name,
        model=GEMINI_MODEL,
        description=description,
        instruction=grounded_instruction,
        tools=[],
        generate_content_config=SAFE_GEN_CONFIG,
        mode="single_turn",
        output_key=output_key,
        output_schema=output_schema,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
