"""Structured state models for the Henry account-research workflow."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Battlecard, IntentSignal, SalesforceAccount, TechnographicIntel


class WorkflowModel(BaseModel):
    """Base contract for mutable workflow state with strict inputs."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class TouchChannel(str, Enum):
    """Supported outbound communication channels."""

    EMAIL = "email"
    PHONE = "phone"
    LINKEDIN = "linkedin"
    VIDEO = "video"


class WorkflowIntent(str, Enum):
    """Top-level user goals supported by the agent."""

    RESEARCH_ACCOUNT = "research_account"
    PRIORITIZE_ACCOUNTS = "prioritize_accounts"
    BUILD_CADENCE = "build_cadence"
    PREPARE_DISCOVERY = "prepare_discovery"
    ASSESS_DEAL_RISK = "assess_deal_risk"


class OutreachTouch(WorkflowModel):
    """One planned step in a multichannel sales sequence."""

    day: int = Field(ge=1, le=90)
    channel: TouchChannel
    persona: str = Field(min_length=2, max_length=100)
    objective: str = Field(min_length=5, max_length=300)
    message: str = Field(min_length=10, max_length=3_000)
    call_to_action: str = Field(min_length=3, max_length=300)


class OutreachCadence(WorkflowModel):
    """Ordered collection of outreach touches for an account."""

    name: str = Field(min_length=3, max_length=120)
    account_name: str = Field(min_length=2, max_length=200)
    touches: list[OutreachTouch] = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=10, max_length=1_000)

    @field_validator("touches")
    @classmethod
    def order_and_validate_touches(
        cls, value: list[OutreachTouch]
    ) -> list[OutreachTouch]:
        """Require unique day/channel pairs and return chronological order."""
        identities = [(touch.day, touch.channel) for touch in value]
        if len(identities) != len(set(identities)):
            raise ValueError("touches must have unique day/channel combinations")
        return sorted(value, key=lambda touch: (touch.day, touch.channel.value))


class ScoredAccount(WorkflowModel):
    """Account enriched with a transparent prioritization score."""

    account: SalesforceAccount
    score: int = Field(ge=0, le=100)
    intent_score: int = Field(ge=0, le=100)
    fit_score: int = Field(ge=0, le=100)
    engagement_score: int = Field(ge=0, le=100)
    rationale: list[str] = Field(min_length=1, max_length=20)
    recommended_action: str = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def score_is_explainable(self) -> ScoredAccount:
        """Ensure the total score is close to the component average."""
        average = round(
            (self.intent_score + self.fit_score + self.engagement_score) / 3
        )
        if abs(self.score - average) > 10:
            raise ValueError("score must be within 10 points of component average")
        return self


class CompetitivePositioning(WorkflowModel):
    """Account-specific positioning assembled from battlecards."""

    competitors: list[str] = Field(default_factory=list, max_length=20)
    battlecards: list[Battlecard] = Field(default_factory=list, max_length=20)
    winning_themes: list[str] = Field(default_factory=list, max_length=20)
    objections: list[str] = Field(default_factory=list, max_length=20)
    talk_track: str | None = Field(default=None, max_length=3_000)

    @field_validator("competitors")
    @classmethod
    def normalize_competitors(cls, value: list[str]) -> list[str]:
        """Remove duplicate competitor names while preserving order."""
        cleaned = [competitor.strip() for competitor in value]
        if any(not competitor for competitor in cleaned):
            raise ValueError("competitors cannot contain blank names")
        return list(dict.fromkeys(cleaned))


class DealRisk(WorkflowModel):
    """A quantified risk that can affect opportunity progression."""

    category: str = Field(min_length=2, max_length=100)
    severity: int = Field(ge=1, le=5)
    description: str = Field(min_length=10, max_length=1_000)
    evidence: list[str] = Field(min_length=1, max_length=20)
    mitigation: str = Field(min_length=10, max_length=1_000)
    owner: str | None = Field(default=None, max_length=100)
    due_date: date | None = None


class DiscoveryBrief(WorkflowModel):
    """Prepared account context and questions for a discovery meeting."""

    account_name: str = Field(min_length=2, max_length=200)
    executive_summary: str = Field(min_length=20, max_length=3_000)
    business_hypotheses: list[str] = Field(min_length=1, max_length=20)
    discovery_questions: list[str] = Field(min_length=1, max_length=30)
    relevant_proof_points: list[str] = Field(default_factory=list, max_length=20)
    attendees: list[str] = Field(default_factory=list, max_length=30)
    desired_outcomes: list[str] = Field(min_length=1, max_length=10)


class HenryAgentState(WorkflowModel):
    """Complete serializable state passed between workflow stages."""

    workflow_intent: WorkflowIntent
    territory: str | None = Field(default=None, max_length=100)
    account_query: str | None = Field(default=None, max_length=200)
    accounts: list[SalesforceAccount] = Field(default_factory=list)
    scored_accounts: list[ScoredAccount] = Field(default_factory=list)
    intent_signals: dict[str, list[IntentSignal]] = Field(default_factory=dict)
    technographics: dict[str, TechnographicIntel] = Field(default_factory=dict)
    competitive_positioning: CompetitivePositioning | None = None
    deal_risks: list[DealRisk] = Field(default_factory=list)
    discovery_brief: DiscoveryBrief | None = None
    outreach_cadence: OutreachCadence | None = None
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Require timezone-aware workflow timestamps."""
        if value.tzinfo is None:
            raise ValueError("updated_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_domain_keys(self) -> HenryAgentState:
        """Ensure enrichment maps are keyed by their record domain."""
        if any(
            signal.domain != domain
            for domain, signals in self.intent_signals.items()
            for signal in signals
        ):
            raise ValueError("intent_signals keys must match signal domains")
        if any(
            intel.domain != domain for domain, intel in self.technographics.items()
        ):
            raise ValueError("technographics keys must match record domains")
        return self
