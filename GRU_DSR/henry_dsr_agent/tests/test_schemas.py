from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from henry_dsr_agent.schemas.agent_state import (
    HenryAgentState,
    OutreachCadence,
    OutreachTouch,
    ScoredAccount,
    TouchChannel,
    WorkflowIntent,
)
from henry_dsr_agent.schemas.models import (
    AccountStatus,
    IntentLevel,
    IntentSignal,
    SalesforceAccount,
    TechnographicIntel,
)
from pydantic import ValidationError


@pytest.fixture
def account() -> SalesforceAccount:
    return SalesforceAccount(
        id="001ABC000000001",
        name="Acme Corporation",
        domain="https://www.Acme.example/path",
        industry="Technology",
        annual_revenue=Decimal("250000000"),
        employee_count=2500,
        territory="West Enterprise",
        account_owner="Avery Rep",
        status=AccountStatus.PROSPECT,
        headquarters="San Francisco, CA",
        current_products=("IdentityIQ", "IdentityIQ"),
    )


def test_account_normalizes_domain_and_products(account: SalesforceAccount) -> None:
    assert account.domain == "acme.example"
    assert account.current_products == ("IdentityIQ",)


@pytest.mark.parametrize("domain", ["localhost", "https://", "has spaces.example"])
def test_account_rejects_invalid_domains(domain: str, account: SalesforceAccount) -> None:
    with pytest.raises(ValidationError):
        SalesforceAccount(**{**account.model_dump(), "domain": domain})


def test_intent_signal_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        IntentSignal(
            domain="acme.example",
            topic="identity governance",
            score=90,
            level=IntentLevel.HIGH,
            buying_stage="evaluation",
            observed_at=datetime(2026, 1, 1),
        )


def test_technographic_record_rejects_future_verification() -> None:
    with pytest.raises(ValidationError, match="future"):
        TechnographicIntel(
            domain="acme.example",
            technologies=("Okta",),
            last_verified_at=date.today() + timedelta(days=1),
        )


def test_cadence_sorts_touches_and_rejects_duplicates() -> None:
    later = OutreachTouch(
        day=5,
        channel=TouchChannel.EMAIL,
        persona="CISO",
        objective="Share relevant proof",
        message="A sufficiently detailed follow-up message.",
        call_to_action="Review the brief",
    )
    earlier = OutreachTouch(
        day=1,
        channel=TouchChannel.LINKEDIN,
        persona="CISO",
        objective="Start a relevant conversation",
        message="A sufficiently detailed opening message.",
        call_to_action="Connect this week",
    )
    cadence = OutreachCadence(
        name="Executive sequence",
        account_name="Acme Corporation",
        touches=[later, earlier],
        rationale="A measured multichannel sequence for the buying team.",
    )
    assert [touch.day for touch in cadence.touches] == [1, 5]
    with pytest.raises(ValidationError, match="unique"):
        cadence.model_copy(update={"touches": [later, later]}).__class__(
            **{**cadence.model_dump(), "touches": [later, later]}
        )


def test_scored_account_requires_explainable_total(account: SalesforceAccount) -> None:
    with pytest.raises(ValidationError, match="component average"):
        ScoredAccount(
            account=account,
            score=95,
            intent_score=20,
            fit_score=30,
            engagement_score=40,
            rationale=["Intent is early"],
            recommended_action="Monitor new intent signals",
        )


def test_state_validates_enrichment_domain_keys(account: SalesforceAccount) -> None:
    signal = IntentSignal(
        domain=account.domain,
        topic="identity governance",
        score=90,
        level=IntentLevel.HIGH,
        buying_stage="evaluation",
        observed_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError, match="keys"):
        HenryAgentState(
            workflow_intent=WorkflowIntent.RESEARCH_ACCOUNT,
            accounts=[account],
            intent_signals={"wrong.example": [signal]},
        )
