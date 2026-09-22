"""Outside-world shapes: news, social, reviews and competitors.

These stand in for the market-intelligence feeds (news APIs, Brandwatch /
Meltwater, G2 / Gartner, competitor pages). The Brand and Campaign Design
orchestrators reason over them; as always the model narrates, it does not
invent, so each item carries the source facts an agent is allowed to use.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Competitor(BaseModel):
    """A named rival in the identity-security category."""

    id: str
    name: str  # Saviynt, CyberArk, One Identity
    category: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    pricing_notes: str = ""
    displacement_angle: str = ""  # how SailPoint wins against them


class Review(BaseModel):
    """A verified third-party review (G2 / Gartner Peer Insights)."""

    id: str
    vendor: str  # SailPoint or a competitor name
    source: str  # "G2", "Gartner Peer Insights"
    rating: float  # out of 5
    role: str  # reviewer's role, e.g. "IAM Director"
    industry: str
    pro: str
    con: str


class NewsItem(BaseModel):
    """A press / trade-media / analyst item the Brand agents monitor."""

    id: str
    published_on: date
    source: str  # "Dark Reading", "PR Newswire", "Gartner", ...
    headline: str
    summary: str
    topics: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)  # SailPoint / competitors
    # Whether this is a spike worth a rapid response (breach, regulation, ...).
    is_trigger_event: bool = False


class SocialMention(BaseModel):
    """A single brand mention on a social platform, with a pre-scored sentiment.

    The sentiment label is carried on the record because in the real system it
    comes from the listening platform (Brandwatch), not from our model. The
    Brand agent aggregates and responds; it does not re-classify from scratch.
    """

    id: str
    platform: str  # LinkedIn, X, Reddit, YouTube
    author_handle: str
    posted_on: date
    text: str
    sentiment: str  # positive, neutral, negative
    mentions: list[str] = Field(default_factory=list)
    followers: int = 0
    needs_response: bool = False


class ShareOfVoiceEntry(BaseModel):
    """Category mention volume for one brand in one period."""

    brand: str
    period: str  # e.g. "2026-Q2"
    mentions: int
    channel: str  # "All", "LinkedIn", "X", "News", ...
