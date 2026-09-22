"""Market intelligence: news, social, reviews, competitors, share of voice."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from ..contracts import Competitor, NewsItem, Review, SocialMention
from ._fixtures import load


class MarketIntelConnector(Protocol):
    def list_competitors(self) -> list[Competitor]: ...
    def list_reviews(self, vendor: str | None = None) -> list[Review]: ...
    def list_news(
        self, trigger_only: bool = False, topic: str | None = None
    ) -> list[NewsItem]: ...
    def list_social_mentions(
        self, platform: str | None = None
    ) -> list[SocialMention]: ...
    def get_share_of_voice(self) -> dict[str, Any]: ...


class MockMarketIntel:
    def list_competitors(self) -> list[Competitor]:
        rows = load("competitors.json")
        return [
            Competitor(
                id=f"COMP-{i}",
                name=r["name"],
                category=r["category"],
                strengths=r.get("strengths", []),
                weaknesses=r.get("weaknesses", []),
                pricing_notes=r.get("pricing_notes", ""),
                displacement_angle=r.get(
                    "displacement_angle",
                    "; ".join(r.get("sailpoint_advantages", [])[:2]),
                ),
            )
            for i, r in enumerate(rows, start=1)
        ]

    def list_reviews(self, vendor: str | None = None) -> list[Review]:
        rows = load("reviews.json")
        out = []
        for i, r in enumerate(rows, start=1):
            product = r.get("product", r.get("vendor", ""))
            if vendor and product.lower() != vendor.lower():
                continue
            out.append(
                Review(
                    id=f"REV-{i}",
                    vendor=product,
                    source=r["source"],
                    rating=float(r["rating"]),
                    role=r.get("reviewer_role", r.get("role", "")),
                    industry=r.get("industry", ""),
                    pro=r.get("pros", r.get("pro", "")),
                    con=r.get("cons", r.get("con", "")),
                )
            )
        return out

    def list_news(
        self, trigger_only: bool = False, topic: str | None = None
    ) -> list[NewsItem]:
        rows = load("news_articles.json")
        out = []
        for r in rows:
            if trigger_only and not r.get("is_trigger", r.get("is_trigger_event")):
                continue
            if topic and topic.lower() not in r.get("topic", "").lower():
                continue
            mentions = []
            if r.get("competitor_mentioned"):
                mentions.append(r["competitor_mentioned"])
            out.append(
                NewsItem(
                    id=r["id"],
                    published_on=date.fromisoformat(r["date"]),
                    source=r["source"],
                    headline=r["headline"],
                    summary=r["summary"],
                    topics=[r.get("topic", "")],
                    mentions=mentions,
                    is_trigger_event=bool(
                        r.get("is_trigger", r.get("is_trigger_event"))
                    ),
                )
            )
        return out

    def list_social_mentions(
        self, platform: str | None = None
    ) -> list[SocialMention]:
        rows = load("social_mentions.json")
        out = []
        for r in rows:
            if platform and r["platform"].lower() != platform.lower():
                continue
            sentiment = r.get("seed_sentiment", r.get("sentiment", "neutral"))
            out.append(
                SocialMention(
                    id=r["id"],
                    platform=r["platform"],
                    author_handle=r.get("author", r.get("author_handle", "")),
                    posted_on=date.fromisoformat(r["date"]),
                    text=r["text"],
                    sentiment=sentiment,
                    mentions=["SailPoint"] if "SailPoint" in r["text"] else [],
                    needs_response=r.get("is_question", False)
                    or sentiment == "negative",
                )
            )
        return out

    def get_share_of_voice(self) -> dict[str, Any]:
        return load("share_of_voice.json")
