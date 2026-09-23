"""Focused checks for the shared role shell."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ui.gateway import create_app as create_gateway
from ui.henry_app import create_app as create_henry
from ui.stuart_app import create_app as create_stuart


class FakeRunner:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def run_async(self, **kwargs):
        message = kwargs["new_message"]
        self.prompts.append("\n".join(part.text or "" for part in message.parts))
        yield Event(
            invocation_id="test",
            author="central_orchestrator",
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="The west forecast needs attention.")],
            ),
        )


class FakeHenry:
    def __init__(self) -> None:
        from henry_dsr_agent.orchestrator import HenryOrchestrator

        real = HenryOrchestrator()
        self.sfdc_tool = real.sfdc_tool
        self.dsr_ask_catalog = real.dsr_ask_catalog
        self.calls: list[dict] = []

    async def chat(self, payload: dict) -> SimpleNamespace:
        self.calls.append(payload)
        return SimpleNamespace(markdown="Apex Financial is showing strong intent.")


def test_stuart_adapter_exposes_workspace_session_and_sse() -> None:
    client = TestClient(
        create_stuart(
            runner=FakeRunner(),
            session_service=InMemorySessionService(),
        )
    )
    workspace = client.get("/api/workspace").json()
    assert workspace["assistant"]["name"] == "Stuart"
    assert len(workspace["tasks"]) == 5

    session_id = client.post("/api/session").json()["session_id"]
    response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "Check the west forecast."},
    )
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert response.headers["x-session-id"] == session_id
    assert any(event["type"] == "reply" for event in events)
    assert events[-1]["type"] == "done"


def test_stuart_offers_filters_and_sends_the_selection_to_the_agent() -> None:
    runner = FakeRunner()
    client = TestClient(
        create_stuart(runner=runner, session_service=InMemorySessionService())
    )
    filters = client.get("/api/workspace").json()["filters"]
    assert set(filters) == {
        "geos",
        "boats",
        "opps",
        "report_types",
        "sizes",
        "stages",
        "windows",
    }
    assert all(filters[key] for key in filters)

    client.post(
        "/api/chat",
        json={
            "message": "Where is the risk?",
            "filters": {"boats": ["David Chen"], "stages": ["SS70"]},
        },
    )
    prompt = runner.prompts[-1]
    assert "Working filters:" in prompt
    assert "Reps: David Chen" in prompt
    assert "SS70 · Proposal & Business Case" in prompt


def test_henry_adapter_exposes_catalog_filters_and_sse() -> None:
    orchestrator = FakeHenry()
    client = TestClient(create_henry(orchestrator=orchestrator))
    workspace = client.get("/api/workspace").json()
    assert workspace["assistant"]["name"] == "Henry"
    assert len(workspace["tasks"]) == 6
    assert sum(len(group["items"]) for group in workspace["tasks"]) == 26
    account = workspace["filters"]["opps"][0]

    response = client.post(
        "/api/chat",
        json={
            "message": "Assess this account",
            "task_id": "account_360_healthcheck",
            "filters": {"opps": [account["id"]], "stages": ["SS20"]},
        },
    )
    assert response.status_code == 200
    assert '"type": "reply"' in response.text
    assert orchestrator.calls[-1]["account_id"] == account["id"]
    assert orchestrator.calls[-1]["action"] == "account_360_healthcheck"
    assert orchestrator.calls[-1]["action_locked"] is True
    assert "Sales stage: SS20" in orchestrator.calls[-1]["message"]


def test_gateway_routes_each_role_and_streams_chat() -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        port = request.url.port
        role = {8091: "Bob", 8092: "James", 8093: "Stuart", 8094: "Henry"}[port]
        if request.url.path == "/api/workspace":
            return httpx.Response(
                200,
                json={"assistant": {"name": role}, "tasks": [], "filters": {}},
            )
        if request.url.path == "/api/dashboard":
            return httpx.Response(
                200,
                json={"copy": {"title": role}, "kpis": {"pipeline": 1, "open_opps": 1, "closing_week": 0, "slack_work": 0}, "filters": {"sizes": [], "stages": [], "windows": [], "geos": []}, "by_stage": [], "by_size": [], "opps": [], "tasks": [], "notifications": [], "slack": []},
            )
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                content=b'data: {"type":"done"}\n\n',
                headers={
                    "Content-Type": "text/event-stream",
                    "X-Session-Id": "session-1",
                },
            )
        raise AssertionError(f"Unexpected upstream request: {request.url}")

    transport = httpx.MockTransport(upstream)
    upstream_client = httpx.AsyncClient(transport=transport)
    with TestClient(create_gateway(client=upstream_client)) as client:
        for role, name in (
            ("bob", "Bob"),
            ("james", "James"),
            ("stuart", "Stuart"),
            ("henry", "Henry"),
        ):
            response = client.get("/api/workspace", params={"role": role})
            assert response.json()["assistant"]["name"] == name
            dash = client.get("/api/dashboard", params={"role": role})
            assert dash.status_code == 200
            assert dash.json()["copy"]["title"] == name
        response = client.post("/api/chat", json={"role": "james", "message": "Hi"})
        assert response.status_code == 200
        assert response.headers["x-session-id"] == "session-1"
        assert '"type":"done"' in response.text


def test_shared_shell_contains_role_switching_contract() -> None:
    with TestClient(create_gateway()) as client:
        chat = client.get("/chat").text
        dash = client.get("/dashboard").text
        script = client.get("/static/app.js").text
        dash_script = client.get("/static/dashboard.js").text
        artifacts = client.get("/static/artifacts.js").text
        home = client.get("/").text
    assert 'id="role-select"' in chat
    assert 'id="role-select"' in dash
    assert '<option value="henry">DSR · Henry</option>' in chat
    assert "role: activeRole" in script
    assert "function chatsKey(" in script
    assert "function loadRole(" in script
    assert "function mapFilterName(" in script
    assert "syncRoleInUrl" in script
    assert "ROLE_AVATARS" in script
    assert "img.src = roleAvatar()" in script
    assert 'getElementById("assistant-avatar")' in script
    assert "`gru-artifacts-${activeRole}`" in artifacts
    assert "function applyAssistant(" in dash_script
    assert "function applyCopy(" in dash_script
    assert "function chatHref(" in dash_script
    assert "/dashboard?role=james" in home
    assert "/dashboard?role=stuart" in home
    assert "/dashboard?role=henry" in home
    assert "/dashboard?role=bob" in home


def test_stuart_and_henry_expose_dashboard_payloads() -> None:
    stuart = TestClient(
        create_stuart(
            runner=FakeRunner(),
            session_service=InMemorySessionService(),
        )
    )
    stuart_dash = stuart.get("/api/dashboard").json()
    assert stuart_dash["copy"]["title"] == "Team forecast"
    assert "kpis" in stuart_dash
    assert "opps" in stuart_dash
    assert "filters" in stuart_dash

    henry = TestClient(create_henry(orchestrator=FakeHenry()))
    henry_dash = henry.get("/api/dashboard").json()
    assert henry_dash["copy"]["title"] == "Account book"
    assert henry_dash["copy"]["kpi_week_filter"] == "stale"
    assert "kpis" in henry_dash
    assert "opps" in henry_dash
