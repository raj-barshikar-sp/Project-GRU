"""Pipeline in the room.

This agent needs exactly the same pipeline maths the Analysis team uses. It
imports it from the shared library rather than asking the Analysis
orchestrator, per the repo convention: delegation is for handing over a task,
importing is for getting a calculation. Asking another agent would add a model
round-trip and a chance for the number to drift, to arrive at the same figure.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.regional_events.events_tools import (
    get_event_attendees,
    get_pipeline_in_accounts,
    list_field_events,
)

from ..prompts import (
    EVENTS_PIPELINE_IN_ROOM_DESCRIPTION,
    EVENTS_PIPELINE_IN_ROOM_INSTRUCTION,
)

pipeline_in_room_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_pipeline_in_room",
    description=EVENTS_PIPELINE_IN_ROOM_DESCRIPTION,
    instruction=EVENTS_PIPELINE_IN_ROOM_INSTRUCTION,
    tools=[list_field_events, get_event_attendees, get_pipeline_in_accounts],
    output_key="events_pipeline_in_room",
)
