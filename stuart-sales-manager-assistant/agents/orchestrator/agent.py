"""Stuart's ADK root agent."""

from __future__ import annotations

import agents.runtime_env  # noqa: F401 — load Vertex quota + ADK flags first

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.activity_engagement_specialist.agent import (
    activity_engagement_specialist_agent,
)
from agents.constants import GEMINI_MODEL, PLANNER_GEN_CONFIG
from agents.crm_intelligence_specialist.agent import crm_intelligence_specialist_agent
from agents.forecast_modeling_specialist.agent import forecast_modeling_specialist_agent
from agents.knowledge_base_rag.agent import knowledge_base_rag_agent
from agents.orchestrator.prompt import build_planner_instruction
from agents.orchestrator.workflow import StuartWorkflow
from agents.rep_performance_specialist.agent import rep_performance_specialist_agent
from agents.synthesis.agent import synthesis_agent
from models.routing_decision import RoutingDecision


def _planner_instruction(context: ReadonlyContext) -> str:
    parts = (context.user_content.parts if context.user_content else None) or []
    request = "\n".join(part.text for part in parts if getattr(part, "text", None))
    return f"{build_planner_instruction()}\n\nTURN INPUT\n{request}"


planner_agent = Agent(
    name="route_planner",
    model=GEMINI_MODEL,
    description=(
        "Stuart's front door. Reads the turn, either answers conversationally "
        "or picks the specialists that own it. Never states business facts."
    ),
    instruction=_planner_instruction,
    generate_content_config=PLANNER_GEN_CONFIG,
    mode="single_turn",
    output_schema=RoutingDecision,
    output_key="routing_decision",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

root_agent = StuartWorkflow(
    name="central_orchestrator",
    description=(
        "Stuart, the sales manager's assistant. Routes each turn to the "
        "specialists that own it and returns one grounded reply."
    ),
    planner_agent=planner_agent,
    final_writer_agent=synthesis_agent,
    sub_agents=[
        planner_agent,
        crm_intelligence_specialist_agent,
        activity_engagement_specialist_agent,
        rep_performance_specialist_agent,
        forecast_modeling_specialist_agent,
        knowledge_base_rag_agent,
        synthesis_agent,
    ],
)
