"""Knowledge-base shapes: the internal facts the generative agents are grounded on.

These stand in for Confluence / Rovo. The point of modelling them is the same as
everywhere else in this system: an agent may only write from facts it was handed,
so the facts need a shape a tool can fetch and hand over.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductFeature(BaseModel):
    """One SailPoint capability, mapped to the buyer problem it addresses."""

    id: str
    module: str  # e.g. "Identity Security Cloud", "Access Modelling"
    capability: str
    description: str
    # The buyer pain this answers. Used by gap/value mapping to match a gap.
    addresses_gap: str
    value_driver: str  # e.g. "audit prep time", "orphaned account risk"


class Persona(BaseModel):
    """A member of the buying committee, with what actually moves them."""

    id: str
    title: str  # e.g. "CISO"
    seniority: str
    priorities: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    # What lands and what falls flat, so messaging stays on-target.
    messaging_do: list[str] = Field(default_factory=list)
    messaging_dont: list[str] = Field(default_factory=list)
    preferred_proof: str = ""  # e.g. "peer case study", "quantified ROI"


class RegulatoryGuide(BaseModel):
    """A compliance regime an agent must reference correctly, not invent."""

    id: str
    name: str  # e.g. "GDPR", "SOX", "NIS2"
    region: str  # AMER, EMEA, APJ, or "Global"
    industries: list[str] = Field(default_factory=list)
    summary: str
    identity_relevance: str  # why identity security matters to this regime


class ICPDefinition(BaseModel):
    """The ideal customer profile, used to score account fit deterministically."""

    industries: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    min_employee_count: int = 0
    min_annual_revenue_usd: int = 0
    priority_titles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
