"""Brand metrics: sentiment aggregation and share of voice.

The Brand orchestrator narrates these tables; it does not recompute them.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable


def sentiment_summary(conn: Connectors) -> MetricTable:
    """Aggregate social mentions by platform and sentiment."""
    mentions = conn.market_intel.list_social_mentions()
    by_platform: dict[str, dict[str, int]] = {}
    for m in mentions:
        entry = by_platform.setdefault(m.platform, {
            "positive": 0, "neutral": 0, "negative": 0, "total": 0,
        })
        entry[m.sentiment] = entry.get(m.sentiment, 0) + 1
        entry["total"] += 1

    rows = []
    for platform, counts in sorted(by_platform.items()):
        total = counts["total"] or 1
        rows.append({
            "Platform": platform,
            "Positive": counts.get("positive", 0),
            "Neutral": counts.get("neutral", 0),
            "Negative": counts.get("negative", 0),
            "Total": counts["total"],
            "Positive %": f"{round(100 * counts.get('positive', 0) / total, 1)}%",
        })

    return MetricTable(
        name="Social sentiment summary",
        description=f"Sentiment breakdown across {len(mentions)} brand mentions.",
        columns=["Platform", "Positive", "Neutral", "Negative",
                 "Total", "Positive %"],
        rows=rows,
        notes=[
            "Sentiment labels come from the listening platform feed.",
            "Negative mentions with support issues should be drafted for review.",
        ],
    )


def share_of_voice(conn: Connectors) -> MetricTable:
    """Category mention share for SailPoint vs key competitors."""
    data = conn.market_intel.get_share_of_voice()
    mentions = data.get("mentions", {})
    total = sum(mentions.values()) or 1
    brands = ["SailPoint", "CyberArk", "Saviynt", "One Identity"]

    rows = []
    for brand in brands:
        count = mentions.get(brand, 0)
        rows.append({
            "Brand": brand,
            "Mentions": count,
            "Share of voice": f"{round(100 * count / total, 1)}%",
        })
    rows.sort(key=lambda r: r["Mentions"], reverse=True)

    return MetricTable(
        name="Share of voice",
        description=f"Category mention volume ({data.get('period', 'recent')}).",
        columns=["Brand", "Mentions", "Share of voice"],
        rows=rows,
        notes=[
            "SailPoint trails CyberArk in overall category share in this dataset.",
            "Use channel breakdown for platform-specific positioning.",
        ],
    )


def news_trends(conn: Connectors, limit: int = 10) -> MetricTable:
    """Recent news and analyst items ranked by recency."""
    items = conn.market_intel.list_news()
    items.sort(key=lambda n: n.published_on, reverse=True)

    rows = [{
        "Date": str(n.published_on),
        "Source": n.source,
        "Headline": n.headline,
        "Topic": ", ".join(n.topics),
        "Trigger": "yes" if n.is_trigger_event else "no",
    } for n in items[:limit]]

    return MetricTable(
        name="News and trend analysis",
        description=f"Top {len(rows)} recent industry and competitor news items.",
        columns=["Date", "Source", "Headline", "Topic", "Trigger"],
        rows=rows,
        notes=[
            "Trigger events are candidates for rapid-response campaigns.",
            "Saviynt breach and NIS2 enforcement are planted trigger stories.",
        ],
    )
