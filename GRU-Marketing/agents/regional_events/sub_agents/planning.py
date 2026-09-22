"""Deciding where to run an event, and who to invite."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.regional_events.events_tools import (
    find_accounts_in_city,
    get_buying_committee,
    get_intent_themes,
    get_unworked_accounts_by_city,
)

from ..prompts import (
    EVENTS_ATTENDEE_TARGETING_DESCRIPTION,
    EVENTS_ATTENDEE_TARGETING_INSTRUCTION,
    EVENTS_LOCATION_TOPIC_DESCRIPTION,
    EVENTS_LOCATION_TOPIC_INSTRUCTION,
)

event_location_topic_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_location_topic",
    description=EVENTS_LOCATION_TOPIC_DESCRIPTION,
    instruction=EVENTS_LOCATION_TOPIC_INSTRUCTION,
    tools=[get_unworked_accounts_by_city, get_intent_themes,
           find_accounts_in_city],
    output_key="events_location_recommendation",
)


attendee_targeting_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="events_attendee_targeting",
    description=EVENTS_ATTENDEE_TARGETING_DESCRIPTION,
    instruction=EVENTS_ATTENDEE_TARGETING_INSTRUCTION,
    tools=[get_buying_committee, find_accounts_in_city],
    output_key="events_target_list",
)
