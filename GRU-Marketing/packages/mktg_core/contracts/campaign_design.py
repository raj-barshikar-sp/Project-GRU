"""Deliverable shapes for the Campaign Design orchestrator.

Campaign ideas, the standardized campaign brief, and competitive battlecards.
Rendered to files by `mktg_core.rendering.artifact`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CampaignIdea(BaseModel):
    """One scored campaign concept."""

    theme: str
    rationale: str  # what signal or gap it answers
    target_audience: str
    channels: list[str] = Field(default_factory=list)
    timing: str = ""
    # A 0-100 score the ideation agent assigns from the evidence it was given.
    score: int = 0
    supporting_evidence: list[str] = Field(default_factory=list)


class CampaignBrief(BaseModel):
    """The standardized planning document that aligns stakeholders."""

    name: str
    goal: str
    target_audience: str
    key_messages: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    budget_usd: int = 0
    timeline: str = ""
    kpis: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class ObjectionHandler(BaseModel):
    objection: str
    response: str


class Battlecard(BaseModel):
    """A "Why SailPoint vs X" competitive card."""

    competitor: str
    positioning_statement: str
    why_we_win: list[str] = Field(default_factory=list)
    their_strengths: list[str] = Field(default_factory=list)
    landmines: list[str] = Field(default_factory=list)
    objection_handlers: list[ObjectionHandler] = Field(default_factory=list)
    displacement_cta: str = ""
