from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from henry_dsr_agent.api.main import create_app
from httpx import ASGITransport, AsyncClient


class FakeOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def accounts(self, **payload: Any) -> list[dict[str, Any]]:
        self.calls.append(("accounts", payload))
        return [{"id": "001", "name": "Acme", "score": 88}]

    async def account_quick_view(self, account_id: str) -> dict[str, Any]:
        self.calls.append(("account_quick_view", {"account_id": account_id}))
        return {
            "account": {"id": account_id, "name": "Acme"},
            "intent": [{"intent_score": 88}],
            "technographics": None,
            "deal_risk": {"risk_level": "low", "risk_score": 0, "flags": []},
        }

    async def territories(self, **payload: Any) -> list[str]:
        self.calls.append(("territories", payload))
        return ["West Enterprise"]

    async def run_workflow(self, workflow: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((workflow, payload))
        return {"message": f"completed {workflow}", "request": payload}

    async def chat(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(("chat", payload))
        return {"message": f"Henry heard: {payload['message']}"}


@pytest.fixture
def orchestrator() -> FakeOrchestrator:
    return FakeOrchestrator()


@pytest_asyncio.fixture
async def client(orchestrator: FakeOrchestrator) -> AsyncClient:
    app = create_app(orchestrator)  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "henry-dsr-agent"}


@pytest.mark.asyncio
async def test_accounts_and_territories_use_orchestrator(
    client: AsyncClient, orchestrator: FakeOrchestrator
) -> None:
    accounts = await client.get("/api/accounts")
    territories = await client.post("/api/territories", json={"territory_id": "west"})
    assert accounts.json()["result"][0]["name"] == "Acme"
    assert territories.json()["result"] == ["West Enterprise"]
    assert [call[0] for call in orchestrator.calls] == ["accounts", "territories"]


@pytest.mark.asyncio
async def test_account_quick_view_aggregates_account_context(
    client: AsyncClient, orchestrator: FakeOrchestrator
) -> None:
    response = await client.get("/api/accounts/001/quick-view")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["account"]["name"] == "Acme"
    assert result["intent"][0]["intent_score"] == 88
    assert result["deal_risk"]["risk_level"] == "low"
    assert orchestrator.calls[-1] == ("account_quick_view", {"account_id": "001"})


@pytest.mark.asyncio
async def test_local_account_quick_view_joins_all_sources() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/api/accounts/001APEXFIN000001/quick-view")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["account"]["name"] == "Apex Financial"
    assert result["intent"][0]["intent_score"] == 94
    assert result["technographics"]["key_contacts"][0]["name"] == "Priya Nair"
    assert result["deal_risk"]["risk_level"] in {"low", "medium", "high"}


@pytest.mark.asyncio
@pytest.mark.parametrize("workflow", ["prospecting", "discovery", "outreach", "deal-risk"])
async def test_workflow_routes(
    client: AsyncClient, orchestrator: FakeOrchestrator, workflow: str
) -> None:
    response = await client.post(
        f"/api/{workflow}",
        json={"message": "help", "account_id": "001", "context": {"persona": "CISO"}},
    )
    assert response.status_code == 200
    assert response.json()["workflow"] == workflow
    assert orchestrator.calls[-1][0] == workflow
    assert orchestrator.calls[-1][1]["account_id"] == "001"


@pytest.mark.asyncio
async def test_chat_validates_and_dispatches(
    client: AsyncClient, orchestrator: FakeOrchestrator
) -> None:
    invalid = await client.post("/api/chat", json={"message": ""})
    assert invalid.status_code == 422
    response = await client.post("/api/chat", json={"message": "next action?", "context": {}})
    assert response.status_code == 200
    assert response.json()["result"]["message"] == "Henry heard: next action?"
    assert orchestrator.calls[-1][0] == "chat"


@pytest.mark.asyncio
async def test_dashboard_and_assets_are_local(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Henry the DSR Minion" in response.text
    assert "sailpoint-logo.svg" in response.text
    assert "assets/henry.png" in response.text
    assert 'id="theme-switch"' in response.text
    assert 'id="toggle-left"' in response.text
    assert 'id="toggle-right"' in response.text
    assert 'id="account-tasks"' in response.text
    assert 'id="task-form"' in response.text
    assert "Next actions" not in response.text
    assert "cdn" not in response.text.lower()
    assert (await client.get("/static/styles.css")).status_code == 200
    assert (await client.get("/static/app.js")).status_code == 200
    assert (await client.get("/static/assets/sailpoint-logo.svg")).status_code == 200
    assert (await client.get("/static/assets/henry.png")).status_code == 200


def test_package_contains_static_assets() -> None:
    static = Path(__file__).parents[1] / "api" / "static"
    assert {path.name for path in static.iterdir()} >= {"index.html", "styles.css", "app.js"}
    assert {path.name for path in (static / "assets").iterdir()} >= {
        "henry.png",
        "sailpoint-logo.svg",
    }
