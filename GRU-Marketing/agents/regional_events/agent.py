"""Regional Event Marketing orchestrator.

Four specialists covering the life of a field event: deciding where to run it,
who to invite, who is coming, and what the room is worth.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from mktg_core.settings import DEFAULT_MODEL, thinking_planner

from .prompts import (
    EVENTS_ORCHESTRATOR_DESCRIPTION,
    EVENTS_ORCHESTRATOR_INSTRUCTION,
)
from .sub_agents import (
    account_brief_pipeline,
    attendee_targeting_agent,
    event_location_topic_agent,
    pipeline_in_room_agent,
)

EVENTS_SPECIALISTS = (
    event_location_topic_agent,
    attendee_targeting_agent,
    account_brief_pipeline,
    pipeline_in_room_agent,
)

regional_events_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_orchestrator",
    description=EVENTS_ORCHESTRATOR_DESCRIPTION,
    instruction=EVENTS_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    # AgentTool, not sub_agents: explicit calls return here, so "where do we run
    # it and who do we invite" runs several specialists in one request instead
    # of ending at the first transfer.
    tools=[AgentTool(agent) for agent in EVENTS_SPECIALISTS],
)

root_agent = regional_events_orchestrator
