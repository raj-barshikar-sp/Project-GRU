import pytest
from henry_dsr_agent.orchestrator import HenryOrchestrator, WorkflowIntent


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Prioritize hot accounts by intent score", WorkflowIntent.PROSPECTING),
        ("Prepare discovery talk track", WorkflowIntent.DISCOVERY),
        ("Draft outreach email", WorkflowIntent.OUTREACH),
        ("Review this stale deal risk", WorkflowIntent.DEAL_RISK),
        ("Tell me about Acme", WorkflowIntent.ACCOUNT),
    ],
)
def test_orchestrator_classifies_public_workflows(
    prompt: str, expected: WorkflowIntent
) -> None:
    assert HenryOrchestrator().classify_intent(prompt) is expected


@pytest.mark.asyncio
async def test_run_resolves_account_id_without_a_preloaded_record() -> None:
    result = await HenryOrchestrator().run(
        "research this account", account_id="001APEXFIN000001"
    )
    assert "Apex Financial" in result.markdown


@pytest.mark.asyncio
async def test_orchestrator_preserves_and_serializes_workflow_state() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.run(
        "Prioritize this prospect by intent score",
        account_id="001",
        context={
            "account": {
                "id": "001",
                "name": "Acme Corporation",
                "domain": "acme.example",
                "industry": "Technology",
                "employee_count": 2500,
                "annual_revenue": 250_000_000,
                "territory": "West",
            },
            "intent": {"score": 90, "buying_stage": "evaluation"},
            "contacts": [],
            "technographics": ["Okta", "Microsoft Entra ID"],
        },
    )
    assert result.intent is WorkflowIntent.PROSPECTING
    assert result.data["intent_score"]["score"] > 0
    assert result.data["account_intel"]["account_name"] == "Acme Corporation"
    assert "request" not in result.data
    assert "Priority" in result.markdown
