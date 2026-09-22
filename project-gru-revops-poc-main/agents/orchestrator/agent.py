"""Builds "root_agent": planner plus SellerCopilotWorkflow."""

from __future__ import annotations

import agents.runtime_env  # noqa: F401 — env must load before agents build

from google.adk.agents import Agent

from agents.constants import GEMINI_MODEL, SAFE_GEN_CONFIG
from agents.orchestrator.domains import DOMAIN_AGENTS
from agents.orchestrator.prompt import build_planner_instruction
from agents.orchestrator.workflow import SellerCopilotWorkflow
from agents.synthesis.agent import synthesis_agent
from models.routing_decision import DomainDecision

planner_agent = Agent(
    name="route_planner",
    model=GEMINI_MODEL,
    description=(
        "Thin RevOps front door. Picks one domain team from child descriptions "
        "or asks one clarifying question. Never answers with numbers."
    ),
    instruction=build_planner_instruction(),
    generate_content_config=SAFE_GEN_CONFIG,
    tools=[],
    output_schema=DomainDecision,
    output_key="domain_decision",
)

root_agent = SellerCopilotWorkflow(
    name="orchestrator",
    description=(
        "Project Gru. Thin front door to six RevOps domain teams, then "
        "tool-bearing specialists, then a free-form markdown reply."
    ),
    planner_agent=planner_agent,
    final_synthesis_agent=synthesis_agent,
    sub_agents=[
        planner_agent,
        *DOMAIN_AGENTS,
        synthesis_agent,
    ],
)
