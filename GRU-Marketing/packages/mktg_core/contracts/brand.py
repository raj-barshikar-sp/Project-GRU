"""Deliverable shapes for the Brand Protection & Social Listening orchestrator.

The drafted social responses and the rapid-response campaign package. Sentiment
counts and share-of-voice percentages are computed in `metrics/brand_metrics.py`
and handed to the agents as tables; only the drafted copy is generative.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DraftedResponse(BaseModel):
    """An on-brand reply to a single mention, held for human review."""

    mention_id: str
    platform: str
    sentiment: str
    suggested_response: str
    visibility: str = "public"  # public or private
    escalate: bool = False


class RapidResponsePackage(BaseModel):
    """A ready-to-deploy reactive campaign built from a trigger event."""

    trigger: str
    angle: str  # SailPoint's point of view on the event
    social_posts: list[str] = Field(default_factory=list)
    blog_outline: list[str] = Field(default_factory=list)
    email_alert_subject: str = ""
    email_alert_body: str = ""
    ad_copy: list[str] = Field(default_factory=list)
    executive_quote: str = ""
