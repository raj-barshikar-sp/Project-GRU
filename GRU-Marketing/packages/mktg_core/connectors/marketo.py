"""Marketo: engagement history, list loads and segment deployment."""

from __future__ import annotations

from typing import Protocol

from ..contracts import DeploymentResult, EngagementEvent
from ._fixtures import load, load_csv


class MarketoConnector(Protocol):
    def list_engagement_events(
        self, account_ids: list[str] | None = None
    ) -> list[EngagementEvent]: ...
    def read_lead_csv(self, filename: str) -> list[dict[str, str]]: ...
    def deploy_segment(
        self, segment_id: str, segment_name: str, contact_count: int
    ) -> DeploymentResult: ...
    def load_list(
        self, list_name: str, rows: list[dict[str, str]]
    ) -> dict[str, object]: ...


class MockMarketo:
    def list_engagement_events(
        self, account_ids: list[str] | None = None
    ) -> list[EngagementEvent]:
        events = [EngagementEvent(**row) for row in load("engagement_events.json")]
        if account_ids is not None:
            wanted = set(account_ids)
            events = [e for e in events if e.account_id in wanted]
        return events

    def read_lead_csv(self, filename: str) -> list[dict[str, str]]:
        return load_csv(filename)

    def deploy_segment(
        self, segment_id: str, segment_name: str, contact_count: int
    ) -> DeploymentResult:
        return DeploymentResult(
            segment_id=segment_id,
            marketo_list_id=f"ML-{abs(hash(segment_id)) % 100_000:05d}",
            contacts_pushed=contact_count,
            message=(
                f"MOCK: would create Marketo smart list '{segment_name}' "
                f"from 6sense segment {segment_id} with {contact_count:,} contacts."
            ),
        )

    def load_list(
        self, list_name: str, rows: list[dict[str, str]]
    ) -> dict[str, object]:
        return {
            "marketo_list_id": f"ML-{abs(hash(list_name)) % 100_000:05d}",
            "list_name": list_name,
            "rows_loaded": len(rows),
            "message": (
                f"MOCK: would upload {len(rows)} cleaned rows into Marketo "
                f"list '{list_name}'."
            ),
        }
