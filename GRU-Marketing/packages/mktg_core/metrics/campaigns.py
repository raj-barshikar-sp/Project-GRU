"""Campaign performance, funnel conversion and week-over-week trends."""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable, Region


def _pct(numerator: int, denominator: int) -> str:
    return f"{round(100 * numerator / denominator, 1)}%" if denominator else "-"


def campaign_performance(conn: Connectors, region: Region | None = None) -> MetricTable:
    """Spend, funnel counts and efficiency for every campaign.

    Cost per opportunity is the column that usually decides the conversation,
    so campaigns are sorted by it, cheapest first.
    """
    campaigns = conn.sfdc.list_campaigns(region)

    rows = []
    for c in campaigns:
        cost_per_opp = int(c.spend_usd / c.opps_created) if c.opps_created else None
        cost_per_mql = int(c.spend_usd / c.mqls) if c.mqls else None
        rows.append({
            "Campaign": c.name,
            "Type": c.type.value,
            "Region": c.region.value,
            "Spend (USD)": c.spend_usd,
            "Leads": c.leads,
            "MQLs": c.mqls,
            "Opps": c.opps_created,
            "Lead>MQL": _pct(c.mqls, c.leads),
            "MQL>Opp": _pct(c.opps_created, c.mqls),
            "Cost per MQL (USD)": cost_per_mql,
            "Cost per opp (USD)": cost_per_opp,
        })

    # Campaigns with no opportunities sort last rather than crashing the sort.
    rows.sort(key=lambda r: r["Cost per opp (USD)"] or 10**12)

    total_spend = sum(c.spend_usd for c in campaigns)
    total_opps = sum(c.opps_created for c in campaigns)

    return MetricTable(
        name="Campaign performance",
        description=(
            f"{len(campaigns)} campaigns"
            + (f" in {region.value}" if region else "")
            + ", sorted by cost per opportunity (best first)."
        ),
        columns=["Campaign", "Type", "Region", "Spend (USD)", "Leads", "MQLs",
                 "Opps", "Lead>MQL", "MQL>Opp", "Cost per MQL (USD)",
                 "Cost per opp (USD)"],
        rows=rows,
        notes=[
            f"Total spend ${total_spend:,} produced {total_opps} opportunities, "
            f"a blended ${int(total_spend / total_opps):,} per opportunity."
            if total_opps else f"Total spend ${total_spend:,}, no opportunities.",
            "Cost per opp is blank where a campaign created no opportunities.",
        ],
    )


def funnel_by_type(conn: Connectors, region: Region | None = None) -> MetricTable:
    """The same funnel, aggregated by campaign type rather than campaign.

    Individual campaigns are noisy; type-level numbers are what a budget
    conversation actually turns on.
    """
    campaigns = conn.sfdc.list_campaigns(region)

    grouped: dict[str, dict[str, int]] = {}
    for c in campaigns:
        bucket = grouped.setdefault(c.type.value, {
            "spend": 0, "leads": 0, "mqls": 0, "sqls": 0, "opps": 0, "count": 0})
        bucket["spend"] += c.spend_usd
        bucket["leads"] += c.leads
        bucket["mqls"] += c.mqls
        bucket["sqls"] += c.sqls
        bucket["opps"] += c.opps_created
        bucket["count"] += 1

    rows = []
    for campaign_type, b in grouped.items():
        rows.append({
            "Campaign type": campaign_type,
            "Campaigns": b["count"],
            "Spend (USD)": b["spend"],
            "Leads": b["leads"],
            "MQLs": b["mqls"],
            "Opps": b["opps"],
            "Lead>MQL": _pct(b["mqls"], b["leads"]),
            "MQL>Opp": _pct(b["opps"], b["mqls"]),
            "Cost per opp (USD)": int(b["spend"] / b["opps"]) if b["opps"] else None,
        })
    rows.sort(key=lambda r: r["Cost per opp (USD)"] or 10**12)

    return MetricTable(
        name="Funnel by campaign type",
        description="Spend and conversion aggregated by channel.",
        columns=["Campaign type", "Campaigns", "Spend (USD)", "Leads", "MQLs",
                 "Opps", "Lead>MQL", "MQL>Opp", "Cost per opp (USD)"],
        rows=rows,
        notes=["Sorted by cost per opportunity, best first."],
    )


def week_over_week(conn: Connectors, region: Region | None = None) -> MetricTable:
    """Change in leads, MQLs and opportunities over the past week."""
    campaigns = conn.sfdc.list_campaigns(region)

    def delta(now: int, before: int) -> str:
        diff = now - before
        if not before:
            return f"+{diff}" if diff else "0"
        return f"{'+' if diff >= 0 else ''}{diff} ({round(100 * diff / before, 1)}%)"

    rows = []
    for c in campaigns:
        rows.append({
            "Campaign": c.name,
            "Leads": c.leads,
            "Leads WoW": delta(c.leads, c.leads_one_week_ago),
            "MQLs": c.mqls,
            "MQLs WoW": delta(c.mqls, c.mqls_one_week_ago),
            "Opps": c.opps_created,
            "Opps WoW": delta(c.opps_created, c.opps_created_one_week_ago),
            "_new_mqls": c.mqls - c.mqls_one_week_ago,
        })
    rows.sort(key=lambda r: r["_new_mqls"], reverse=True)
    for row in rows:
        row.pop("_new_mqls")

    new_leads = sum(c.leads - c.leads_one_week_ago for c in campaigns)
    new_mqls = sum(c.mqls - c.mqls_one_week_ago for c in campaigns)
    new_opps = sum(c.opps_created - c.opps_created_one_week_ago for c in campaigns)

    return MetricTable(
        name="Week-over-week campaign movement",
        description="Change in each campaign's funnel over the past seven days.",
        columns=["Campaign", "Leads", "Leads WoW", "MQLs", "MQLs WoW",
                 "Opps", "Opps WoW"],
        rows=rows,
        notes=[
            f"Across all campaigns in scope: +{new_leads} leads, "
            f"+{new_mqls} MQLs, +{new_opps} opportunities this week.",
            "Sorted by new MQLs added, highest first.",
        ],
    )


def spend_efficiency_outliers(conn: Connectors) -> MetricTable:
    """The best and worst campaigns by cost per opportunity.

    Isolating the extremes is what turns an analysis into a recommendation:
    it makes the budget-shift argument concrete rather than general.
    """
    campaigns = conn.sfdc.list_campaigns()
    with_opps = [c for c in campaigns if c.opps_created > 0]
    with_opps.sort(key=lambda c: c.spend_usd / c.opps_created)

    best = with_opps[:3]
    worst = list(reversed(with_opps[-3:]))
    no_opps = [c for c in campaigns if c.opps_created == 0]

    rows = []
    for label, group in (("Most efficient", best), ("Least efficient", worst)):
        for c in group:
            rows.append({
                "Band": label,
                "Campaign": c.name,
                "Type": c.type.value,
                "Spend (USD)": c.spend_usd,
                "Opps": c.opps_created,
                "Cost per opp (USD)": int(c.spend_usd / c.opps_created),
            })
    for c in no_opps:
        rows.append({
            "Band": "No opportunities",
            "Campaign": c.name,
            "Type": c.type.value,
            "Spend (USD)": c.spend_usd,
            "Opps": 0,
            "Cost per opp (USD)": None,
        })

    notes = []
    if best and worst:
        cheapest = best[0]
        priciest = worst[0]
        ratio = round(
            (priciest.spend_usd / priciest.opps_created)
            / (cheapest.spend_usd / cheapest.opps_created), 1)
        notes.append(
            f"'{priciest.name}' costs {ratio}x more per opportunity than "
            f"'{cheapest.name}'."
        )
        notes.append(
            f"Moving spend from the least to the most efficient campaign would, "
            f"at the efficient rate, buy roughly "
            f"{int(priciest.spend_usd / (cheapest.spend_usd / cheapest.opps_created))}"
            f" opportunities for the same ${priciest.spend_usd:,}."
        )

    return MetricTable(
        name="Spend efficiency outliers",
        description="Best and worst campaigns by cost per opportunity.",
        columns=["Band", "Campaign", "Type", "Spend (USD)", "Opps",
                 "Cost per opp (USD)"],
        rows=rows,
        notes=notes,
    )
