"""Canonical data contracts for CRM and market-intelligence sources."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_domain(value: str) -> str:
    """Normalize and validate an internet domain."""
    if not isinstance(value, str):
        raise TypeError("domain must be a string")
    domain = value.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]
    domain = domain.split("/", maxsplit=1)[0].removeprefix("www.").rstrip(".")
    if not _DOMAIN_PATTERN.fullmatch(domain):
        raise ValueError("must be a valid domain name")
    return domain


class StrictModel(BaseModel):
    """Base model shared by immutable, strict external-data contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class AccountStatus(str, Enum):
    """Supported CRM lifecycle stages."""

    PROSPECT = "prospect"
    CUSTOMER = "customer"
    CHURNED = "churned"


class IntentLevel(str, Enum):
    """Normalized purchase-intent strength."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SalesforceAccount(StrictModel):
    """Canonical Salesforce account used by every DSR workflow."""

    id: str = Field(min_length=3, max_length=18)
    name: str = Field(min_length=2, max_length=200)
    domain: str
    industry: str = Field(min_length=2, max_length=100)
    annual_revenue: float = Field(ge=0)
    employee_count: int = Field(ge=1)
    owner_id: str = Field(min_length=2, max_length=100)
    territory: str = Field(min_length=2, max_length=100)
    target_tier: str = Field(min_length=1, max_length=30)
    stage: str | None = Field(default=None, max_length=30)
    last_activity_date: str
    bva_complete: bool = False
    days_in_stage: int = Field(default=0, ge=0)
    stakeholder_count: int = Field(default=1, ge=0)
    current_products: tuple[str, ...] = ()
    open_opportunity_amount: float = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_input(cls, value: object) -> object:
        """Accept earlier fixture keys while serializing the canonical contract."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data["domain"] = normalize_domain(str(data.get("domain", "")))
        data.setdefault("owner_id", data.pop("account_owner", "unassigned"))
        legacy_status = data.pop("status", "")
        data.setdefault("target_tier", "Customer" if legacy_status == "customer" else "Tier 1")
        data.setdefault("stage", None)
        legacy_date = data.pop("last_activity_at", None)
        data.setdefault("last_activity_date", str(legacy_date or date.today().isoformat())[:10])
        data["current_products"] = list(dict.fromkeys(data.get("current_products", [])))
        data.pop("headquarters", None)
        return data

    @property
    def last_activity_at(self) -> datetime:
        """Expose a datetime for scoring clients written against the prior contract."""
        return datetime.fromisoformat(self.last_activity_date).replace(tzinfo=timezone.utc)

    @property
    def account_owner(self) -> str:
        """Compatibility alias for display clients."""
        return self.owner_id

    @property
    def bva(self) -> dict[str, bool] | None:
        """Expose completed value-case evidence to the deal-risk specialist."""
        return {"complete": True} if self.bva_complete else None

    @property
    def stakeholders(self) -> list[str]:
        """Represent the current number of engaged buying-committee members."""
        return [f"stakeholder-{index}" for index in range(self.stakeholder_count)]


class IntentSignal(StrictModel):
    """Canonical 6sense/TechTarget intent snapshot."""

    domain: str
    buying_stage: str = Field(pattern=r"^(Awareness|Consideration|Decision)$")
    intent_score: int = Field(ge=0, le=100)
    intent_topics: list[str] = Field(min_length=1)
    profile_fit: str = Field(pattern=r"^(Strong|Moderate|Weak)$")
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "6sense"

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_input(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data["domain"] = normalize_domain(str(data.get("domain", "")))
        data.setdefault("intent_score", data.pop("score", 0))
        topic = data.pop("topic", None)
        data.setdefault("intent_topics", [topic] if topic else ["Identity security"])
        level = str(data.pop("level", "")).lower()
        data.setdefault("profile_fit", "Strong" if level in {"high", "very_high"} else "Moderate")
        if topic and str(data.get("buying_stage", "")).lower() == "evaluation":
            data["buying_stage"] = "Consideration"
        return data

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)

    @property
    def score(self) -> int:
        return self.intent_score

    @property
    def topic(self) -> str:
        return self.intent_topics[0]

    @property
    def level(self) -> IntentLevel:
        return IntentLevel.VERY_HIGH if self.intent_score >= 90 else (
            IntentLevel.HIGH if self.intent_score >= 75 else IntentLevel.MEDIUM
        )


class ContactPersona(StrictModel):
    """Buying-committee contact for identity-security outreach."""

    name: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=150)
    email: str
    seniority: str = Field(min_length=2, max_length=50)
    department: str = Field(min_length=2, max_length=100)
    linkedin_url: str | None = None
    location: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_contact(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data.setdefault("name", data.pop("full_name", None))
        email = str(data.get("email", "")).strip().lower()
        if not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError("must be a valid email address")
        data["email"] = email
        return data

    @property
    def full_name(self) -> str:
        return self.name


class TechnographicIntel(StrictModel):
    """Canonical ZoomInfo technographic and buying-committee snapshot."""

    domain: str
    installed_technologies: list[str] = Field(min_length=1)
    it_security_headcount: int = Field(ge=0)
    key_contacts: list[ContactPersona] = Field(default_factory=list)
    last_verified_at: date = Field(default_factory=date.today)
    source: str = "ZoomInfo"

    @model_validator(mode="before")
    @classmethod
    def normalize_intel(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data["domain"] = normalize_domain(str(data.get("domain", "")))
        data.setdefault("installed_technologies", data.pop("technologies", []))
        data.setdefault("key_contacts", data.pop("contacts", []))
        data.setdefault("it_security_headcount", 0)
        technologies = [str(item).strip() for item in data["installed_technologies"]]
        if any(not technology for technology in technologies):
            raise ValueError("technologies cannot contain blank values")
        data["installed_technologies"] = list(dict.fromkeys(technologies))
        return data

    @property
    def technologies(self) -> tuple[str, ...]:
        return tuple(self.installed_technologies)

    @property
    def contacts(self) -> tuple[ContactPersona, ...]:
        return tuple(self.key_contacts)

    @field_validator("last_verified_at")
    @classmethod
    def verification_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("last_verified_at cannot be in the future")
        return value


class Battlecard(StrictModel):
    """Approved identity-security displacement guidance."""

    competitor_name: str = Field(min_length=2, max_length=100)
    weaknesses: list[str] = Field(min_length=1)
    kill_points: str = Field(min_length=5)
    trap_questions: list[str] = Field(min_length=1)
    value_hook: str = Field(min_length=5)
    source: str = "Local battlecard"

    @model_validator(mode="before")
    @classmethod
    def normalize_card(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data.setdefault("competitor_name", data.pop("competitor", None))
        differentiators = data.pop("differentiators", [])
        default_kill_points = "; ".join(differentiators) or "Lead with governance outcomes."
        data.setdefault("kill_points", default_kill_points)
        data.setdefault("trap_questions", data.pop("discovery_questions", []))
        data.setdefault("value_hook", data.pop("summary", "Simplify identity security outcomes."))
        data.pop("strengths", None)
        data.pop("landmines", None)
        data.pop("proof_points", None)
        data.pop("last_updated", None)
        return data

    @property
    def competitor(self) -> str:
        return self.competitor_name

    @property
    def differentiators(self) -> tuple[str, ...]:
        return (self.kill_points, self.value_hook)

    @property
    def landmines(self) -> tuple[str, ...]:
        return tuple(self.trap_questions)
