"""Read-only tools for the Content Generation orchestrator."""

from __future__ import annotations

from mktg_core.rendering.artifact import describe_saved, save_artifact
from tools._shared._common import conn


def get_brand_voice_guide() -> str:
    """SailPoint brand voice, tone rules and banned phrases."""
    voice = conn().kb.get_brand_voice()
    lines = [
        "### Brand voice",
        f"**Tone:** {', '.join(voice.get('tone', []))}",
        "",
        "**Style rules:**",
    ]
    lines += [f"- {r}" for r in voice.get("style_rules", [])]
    lines += ["", "**Banned phrases:** " + ", ".join(voice.get("banned_phrases", []))]
    if voice.get("boilerplate"):
        lines += ["", f"**Boilerplate:** {voice['boilerplate']}"]
    return "\n".join(lines)


def get_anchor_asset_outline() -> str:
    """Standard sections for a long-form anchor asset."""
    templates = conn().kb.get_templates()
    sections = templates.get("anchor_asset", [])
    return "Anchor asset sections:\n" + "\n".join(f"- {s}" for s in sections)


def get_regional_glossary(region: str) -> str:
    """Regulatory and terminology context for localization.

    Args:
        region: EMEA, APJ, LATAM, or all.

    Returns:
        Regulations and localization notes for the region.
    """
    regs = conn().kb.list_regulations()
    r = region.strip().upper()
    lines = [f"### Regional glossary - {region}", ""]
    for reg in regs:
        if r not in {"ALL", ""} and reg.region not in {r, "Global"}:
            continue
        lines += [f"**{reg.name}:** {reg.summary}", ""]
    return "\n".join(lines)


def get_channel_specs() -> str:
    """Character limits and format rules per channel."""
    return """### Channel specs

| Channel | Limit | Notes |
|---|---|---|
| LinkedIn post | 3,000 chars | Lead with the insight, not the product |
| X post | 280 chars | One idea per post |
| Email subject | 50 chars | Personalize with account or industry |
| Paid search headline | 30 chars | Include primary keyword |
| Blog | 800-1,200 words | H2 every 200 words |
| Sales one-pager | 400 words | Bullets, one proof point per section |
"""


def save_content_artifact(artifact_json: str, artifact_type: str,
                          filename: str) -> str:
    """Save anchor asset, asset grid or localized content.

    Args:
        artifact_json: JSON for the deliverable.
        artifact_type: anchor_asset, asset_grid, or localized.
        filename: Output filename.

    Returns:
        Where the file was saved.
    """
    result = save_artifact(artifact_json, artifact_type, filename)
    return describe_saved(result)


CONTENT_TOOLS = [
    get_brand_voice_guide,
    get_anchor_asset_outline,
    get_regional_glossary,
    get_channel_specs,
    save_content_artifact,
]
