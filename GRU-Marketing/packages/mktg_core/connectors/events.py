"""Field events and their attendee lists.

In the real world this is part of Salesforce Campaign Members; it is separated
here because the Regional Events orchestrator is the only consumer.
"""

from __future__ import annotations

from typing import Protocol

from ..contracts import EventAttendee, FieldEvent
from ._fixtures import load


class EventsConnector(Protocol):
    def list_events(self) -> list[FieldEvent]: ...
    def list_attendees(self, event_id: str) -> list[EventAttendee]: ...


class MockEvents:
    def list_events(self) -> list[FieldEvent]:
        return [FieldEvent(**row) for row in load("field_events.json")]

    def list_attendees(self, event_id: str) -> list[EventAttendee]:
        return [
            EventAttendee(**row)
            for row in load("event_attendees.json")
            if row["event_id"] == event_id
        ]
