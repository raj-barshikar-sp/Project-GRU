"""Read-only tools for the Campaign Design orchestrator."""

from __future__ import annotations

from mktg_core import metrics
from mktg_core.rendering.artifact import describe_saved, save_artifact
from tools._shared._common import REGION_HELP, conn, parse_region


def get_pipeline_gaps_for_ideation(region: str) -> str:
    """Pipeline coverage gaps and unworked account clusters for campaign ideas.

    Args:
        region: {region_help}

    Returns:
        Coverage by region plus unworked account clusters with intent themes.
    """
    c = conn()
    coverage = metrics.coverage_by_region(c).to_markdown()
    unworked = metrics.accounts_without_opportunity(
        c, parse_region(region)).to_markdown()
    return coverage + "\n\n" + unworked


def get_campaign_performance_signals(region: str) -> str:
    """How existing campaigns performed, to inform new campaign design.

    Args:
        region: {region_help}

    Returns:
        Campaign performance and spend efficiency outliers.
    """
    c = conn()
    perf = metrics.campaign_performance(c, parse_region(region)).to_markdown()
    outliers = metrics.spend_efficiency_outliers(c).to_markdown()
    return perf + "\n\n" + outliers


def get_competitor_intelligence(competitor: str) -> str:
    """Competitor strengths, weaknesses and displacement angles.

    Args:
        competitor: CyberArk, Saviynt, One Identity, or all.

    Returns:
        Competitor profiles and G2/Gartner review summaries.
    """
    c = conn()
    comps = c.market_intel.list_competitors()
    if competitor.strip().lower() != "all":
        comps = [x for x in comps if x.name.lower() == competitor.strip().lower()]
    lines = []
    for comp in comps:
        reviews = c.market_intel.list_reviews(comp.name)
        lines += [
            f"### {comp.name}",
            f"Category: {comp.category}",
            f"Displacement angle: {comp.displacement_angle}",
            "",
            "**Strengths:** " + "; ".join(comp.strengths),
            "**Weaknesses:** " + "; ".join(comp.weaknesses),
            "",
        ]
        if reviews:
            lines += ["**Reviews:**"]
            for r in reviews[:3]:
                lines.append(
                    f"- {r.source} ({r.rating}/5, {r.role}): +{r.pro} / -{r.con}")
            lines.append("")
    return "\n".join(lines) if lines else f"No competitor data for {competitor!r}."


def get_campaign_brief_template() -> str:
    """Standard campaign brief sections from the knowledge base."""
    templates = conn().kb.get_templates()
    sections = templates.get("campaign_brief", [])
    return "Campaign brief sections:\n" + "\n".join(f"- {s}" for s in sections)


def get_named_campaign(name: str) -> str:
    """Look up one campaign by name or id so a brief or deck can be grounded.

    Args:
        name: Campaign name or id, for example "Cloud Security Always On"
            or "CMP-001".

    Returns:
        Name, type, region, dates, spend and funnel counts, or a short
        list of close matches if nothing exact is found.
    """
    needle = name.strip().lower()
    campaigns = conn().sfdc.list_campaigns()
    exact = [
        item for item in campaigns
        if needle in item.name.lower() or needle == item.id.lower()
    ]
    if not exact and needle:
        exact = [
            item for item in campaigns
            if all(part in item.name.lower() for part in needle.split() if len(part) > 2)
        ]
    if not exact:
        listed = ", ".join(item.name for item in campaigns[:8])
        return f"No campaign matched {name!r}. Known campaigns include: {listed}."
    lines = []
    for item in exact[:5]:
        lines += [
            f"### {item.name}",
            f"Id: {item.id}",
            f"Type: {item.type.value}",
            f"Region: {item.region.value}",
            f"Dates: {item.start_date.isoformat()} to {item.end_date.isoformat()}",
            f"Spend (USD): {item.spend_usd}",
            f"Leads: {item.leads}",
            f"MQLs: {item.mqls}",
            f"SQLs: {item.sqls}",
            f"Opps: {item.opps_created}",
            "",
        ]
    return "\n".join(lines).strip()


def get_product_priorities() -> str:
    """SailPoint product capabilities for messaging alignment."""
    features = conn().kb.list_product_features()
    lines = ["### Product capabilities", ""]
    for f in features:
        lines.append(f"- **{f.capability}**: {f.description} (addresses: {f.addresses_gap})")
    return "\n".join(lines)


def save_campaign_artifact(artifact_json: str, artifact_type: str,
                           filename: str) -> str:
    """Save a campaign brief or battlecard to disk.

    Args:
        artifact_json: JSON for the deliverable.
        artifact_type: campaign_brief or battlecard.
        filename: Output filename.

    Returns:
        Where the file was saved.
    """
    result = save_artifact(artifact_json, artifact_type, filename)
    return describe_saved(result)


for _fn in (get_pipeline_gaps_for_ideation, get_campaign_performance_signals,):
    _fn.__doc__ = _fn.__doc__.replace("{region_help}", REGION_HELP)

CAMPAIGN_DESIGN_TOOLS = [
    get_pipeline_gaps_for_ideation,
    get_campaign_performance_signals,
    get_competitor_intelligence,
    get_campaign_brief_template,
    get_named_campaign,
    get_product_priorities,
    save_campaign_artifact,
]
