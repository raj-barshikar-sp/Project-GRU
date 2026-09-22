"""Factory for single-turn specialists and no-tool domain orchestrators."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from google.adk.agents import Agent
from pydantic import BaseModel

from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG

REPLY_CONTRACT = """
After tools run, fill the structured schema and write reply as markdown the
AE can read. You choose the structure that fits this ask — do not use a
fixed Summary / Key insights / Recommended actions / Artifacts template.
Do not invent numbers. Never name tools, files, CSV/JSON tables, or other
agents in customer-facing copy.
""".strip()


def make_specialist(
    *,
    name: str,
    description: str,
    instruction: str,
    tools: Sequence[Callable[..., Any]],
    output_schema: type[BaseModel],
    output_key: str,
) -> Agent:
    """Flash specialist: tools first, structured JSON, no chat transfer."""
    return Agent(
        name=name,
        model=GEMINI_MODEL,
        description=description,
        instruction=f"{instruction}\n\n{REPLY_CONTRACT}",
        tools=list(tools),
        generate_content_config=SAFE_GEN_CONFIG,
        mode="single_turn",
        output_key=output_key,
        output_schema=output_schema,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def make_domain_orchestrator(
    *,
    name: str,
    description: str,
    instruction: str,
    sub_agents: Sequence[Agent],
) -> Agent:
    """No-tool domain router. ADK routes on the agent description field, not comments."""
    return Agent(
        name=name,
        model=GEMINI_MODEL,
        description=description,
        instruction=instruction,
        tools=[],
        generate_content_config=SAFE_GEN_CONFIG,
        sub_agents=list(sub_agents),
        disallow_transfer_to_parent=True,
    )
