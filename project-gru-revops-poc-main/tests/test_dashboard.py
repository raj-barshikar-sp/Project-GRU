"""Dummy Salesforce / Slack dashboard filters."""

from datetime import date

from fastapi.testclient import TestClient

from ui.app import create_app
from ui.dashboard import dashboard_payload


TODAY = date(2026, 9, 17)


def test_dashboard_payload_filters_size_stage_time() -> None:
    book = dashboard_payload(today=TODAY)
    assert book["opps"]
    assert book["kpis"]["open_opps"] >= 1
    assert all(item["work"] for item in book["slack"])
    assert not any("lunch" in item["text"].lower() for item in book["slack"])
    assert book["tasks"]
    stamps = [row["due_at"] for row in book["tasks"]]
    assert stamps == sorted(stamps)
    assert all(row["due"] for row in book["tasks"])
    assert book["artifacts"]

    sized = dashboard_payload(sizes=["enterprise"], today=TODAY)
    assert sized["opps"]
    assert all(row["size"] == "enterprise" for row in sized["opps"])
    assert sized["kpis"]["open_opps"] <= book["kpis"]["open_opps"]

    staged = dashboard_payload(stages=["SS20"], today=TODAY)
    assert staged["opps"]
    assert all(row["stage"] == "SS20" for row in staged["opps"])

    week = dashboard_payload(windows=["this_week"], today=TODAY)
    assert week["opps"]
    assert all(row["close_date"] >= "2026-09-14" and row["close_date"] < "2026-09-21" for row in week["opps"])


def test_dashboard_api_and_workspace_filters() -> None:
    client = TestClient(create_app())
    payload = client.get("/api/dashboard?sizes=smb&stages=SS40").json()
    assert payload["filters"]["sizes"]
    assert payload["filters"]["stages"]
    assert payload["filters"]["windows"]
    assert all(row["size"] == "smb" for row in payload["opps"])
    assert all(row["stage"] == "SS40" for row in payload["opps"])

    workspace = client.get("/api/workspace").json()
    assert {item["id"] for item in workspace["filters"]["sizes"]} == {"smb", "mid", "enterprise"}
    assert "SS20" in {item["id"] for item in workspace["filters"]["stages"]}
    assert "this_week" in {item["id"] for item in workspace["filters"]["windows"]}
