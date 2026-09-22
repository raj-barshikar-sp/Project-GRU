"""Account-enrichment shapes: technographics and company facts.

These stand in for ZoomInfo / Cognism / BuiltWith and SEC / business-news
feeds. The ABM Intel and Gap/Value agents read them to ground research and to
find the gaps SailPoint can fill.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Technographic(BaseModel):
    """An installed technology detected at an account."""

    account_id: str
    category: str  # IGA, PAM, IAM, ITSM, SIEM, MFA
    vendor: str
    # Free-text status; "legacy" and "manual" are the words the gap analysis
    # keys on to decide something is a weakness.
    status: str = "current"  # current, legacy, manual, none


class CompanyFacts(BaseModel):
    """Business context on an account, beyond the CRM firmographics."""

    account_id: str
    revenue_growth_pct: float | None = None
    recent_leadership_change: str = ""
    recent_news: str = ""
    strategic_priorities: list[str] = Field(default_factory=list)
    compliance_drivers: list[str] = Field(default_factory=list)
