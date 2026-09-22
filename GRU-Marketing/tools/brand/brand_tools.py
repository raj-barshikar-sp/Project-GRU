"""Read-only tools for the Brand orchestrator."""

from __future__ import annotations

from mktg_core import metrics
from mktg_core.rendering.artifact import describe_saved, save_artifact
from tools._shared._common import conn


def get_social_sentiment() -> str:
    """Sentiment breakdown of brand mentions across social platforms.

    Returns:
        A markdown table of positive, neutral and negative mentions by platform.
    """
    return metrics.sentiment_summary(conn()).to_markdown()


def get_share_of_voice() -> str:
    """SailPoint share of voice vs CyberArk, Saviynt and One Identity.

    Returns:
        A markdown table of mention volume and category share.
    """
    return metrics.share_of_voice(conn()).to_markdown()


def get_news_trends() -> str:
    """Recent industry news, analyst commentary and trigger events.

    Returns:
        A markdown table of news items ranked by date.
    """
    return metrics.news_trends(conn()).to_markdown()


def get_brand_response_playbook() -> str:
    """Brand voice rules and escalation guidance for public responses."""
    voice = conn().kb.get_brand_voice()
    lines = [
        "### Response playbook",
        "",
        "**Tone:** " + ", ".join(voice.get("tone", [])),
        "",
        "Rules:",
    ]
    lines += [f"- {r}" for r in voice.get("style_rules", [])]
    lines += [
        "",
        "Escalate to PR when: competitor breach mentioned, legal threat, "
        "or sustained negative sentiment spike.",
    ]
    return "\n".join(lines)


def get_trigger_events() -> str:
    """News items flagged as rapid-response trigger events.

    Returns:
        Trigger headlines with summaries.
    """
    items = conn().market_intel.list_news(trigger_only=True)
    if not items:
        return "No trigger events in the current feed."
    lines = ["### Trigger events", ""]
    for n in items:
        lines += [f"**{n.headline}** ({n.source}, {n.published_on})",
                  n.summary, ""]
    return "\n".join(lines)


def get_executive_voices() -> str:
    """Pre-approved executive quote templates for rapid response."""
    voices = conn().kb.list_executive_voices()
    lines = ["### Executive voices", ""]
    for v in voices:
        lines += [
            f"**{v['name']}** - {v['title']}",
            f"Themes: {', '.join(v.get('themes', []))}",
            f"Sample: {v.get('sample_quote', '')}",
            "",
        ]
    return "\n".join(lines)


def save_brand_artifact(artifact_json: str, filename: str) -> str:
    """Save a rapid-response campaign package.

    Args:
        artifact_json: JSON matching RapidResponsePackage.
        filename: Output filename.

    Returns:
        Where the file was saved.
    """
    result = save_artifact(artifact_json, "rapid_response", filename)
    return describe_saved(result)


BRAND_TOOLS = [
    get_social_sentiment,
    get_share_of_voice,
    get_news_trends,
    get_brand_response_playbook,
    get_trigger_events,
    get_executive_voices,
    save_brand_artifact,
]
