"""Deliverable shapes for the Content Generation orchestrator.

Anchor assets, their derivative asset grids, localized variants, and
campaign-type content packages. Rendered to files by
`mktg_core.rendering.artifact`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AssetSection(BaseModel):
    heading: str
    body: str


class AnchorAsset(BaseModel):
    """A long-form content pillar: whitepaper, e-book or executive guide."""

    title: str
    asset_type: str  # Whitepaper, E-book, Executive Guide
    audience: str = ""
    executive_summary: str = ""
    sections: list[AssetSection] = Field(default_factory=list)
    cta: str = ""


class AssetGridItem(BaseModel):
    """One derivative piece deconstructed from the anchor asset."""

    channel: str  # Blog, LinkedIn, X, Email, Paid Search, Sales One-Pager, Webinar
    format: str
    headline: str
    body: str
    notes: str = ""  # character limits observed, etc.


class AssetGrid(BaseModel):
    """The full matrix of derivatives mapped across channels."""

    source_asset: str
    items: list[AssetGridItem] = Field(default_factory=list)


class LocalizedAsset(BaseModel):
    """An asset adapted for a target language and region."""

    title: str
    language: str
    region: str  # EMEA, APJ, LATAM, ...
    body: str
    localization_notes: list[str] = Field(default_factory=list)
    regulatory_references: list[str] = Field(default_factory=list)


class CampaignVariantPackage(BaseModel):
    """A content package for a specific campaign type.

    Covers Product Launch, Global, Regional, Industry and Competitive variants
    with one flexible shape rather than five near-identical models.
    """

    variant: str  # Product Launch, Global, Regional, Industry, Competitive
    title: str
    audience: str = ""
    pieces: list[AssetGridItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
