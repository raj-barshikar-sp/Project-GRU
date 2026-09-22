"""Pipeline health: coverage against target, stage mix and stalled deals.

Every number an agent quotes about pipeline is computed here. Agents narrate
these tables; they never recompute them.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import OPEN_STAGES, MetricTable, OppStage, Opportunity, Region


def _open(opps: list[Opportunity]) -> list[Opportunity]:
    return [o for o in opps if o.is_open]


def coverage_by_region(conn: Connectors) -> MetricTable:
    """Open pipeline divided by quarterly target, per region.

    Coverage is the ratio of open pipeline to the number you have to close.
    A 2x target means carrying twice as much pipeline as quota, on the
    assumption that roughly half of it will not close.
    """
    opps = conn.sfdc.list_opportunities()
    target_multiple = conn.tableau.coverage_target_multiple()
    targets = conn.tableau.all_targets()

    rows = []
    for region in Region:
        region_opps = _open([o for o in opps if o.owner_region == region])
        open_amount = sum(o.amount_usd for o in region_opps)
        target = targets.get(region.value, 0)
        coverage = round(open_amount / target, 2) if target else 0.0
        gap = max(0, int(target * target_multiple) - open_amount)
        rows.append({
            "Region": region.value,
            "Open pipeline (USD)": open_amount,
            "Quarterly target (USD)": target,
            "Coverage": f"{coverage}x",
            "Meets 2x target": coverage >= target_multiple,
            "Gap to target (USD)": gap,
            "Open opps": len(region_opps),
        })

    total_open = sum(r["Open pipeline (USD)"] for r in rows)
    total_target = sum(r["Quarterly target (USD)"] for r in rows)
    rows.append({
        "Region": "TOTAL",
        "Open pipeline (USD)": total_open,
        "Quarterly target (USD)": total_target,
        "Coverage": f"{round(total_open / total_target, 2) if total_target else 0}x",
        "Meets 2x target": (total_open / total_target if total_target else 0)
        >= target_multiple,
        "Gap to target (USD)": max(0, int(total_target * target_multiple) - total_open),
        "Open opps": sum(r["Open opps"] for r in rows),
    })

    return MetricTable(
        name="Pipeline coverage by region",
        description="Open pipeline against quarterly target.",
        columns=["Region", "Open pipeline (USD)", "Quarterly target (USD)",
                 "Coverage", "Meets 2x target", "Gap to target (USD)", "Open opps"],
        rows=rows,
        notes=[
            f"Coverage target is {target_multiple}x.",
            "Coverage = open pipeline / quarterly target.",
            "Gap = (target x multiple) - open pipeline, floored at zero.",
            "Open excludes Closed Won and Closed Lost.",
        ],
    )


def stage_distribution(conn: Connectors, region: Region | None = None) -> MetricTable:
    """How pipeline value and count sit across the stages."""
    opps = _open(conn.sfdc.list_opportunities(region))
    total_value = sum(o.amount_usd for o in opps) or 1

    rows = []
    for stage in OPEN_STAGES:
        at_stage = [o for o in opps if o.stage == stage]
        value = sum(o.amount_usd for o in at_stage)
        rows.append({
            "Stage": stage.value,
            "Opps": len(at_stage),
            "Value (USD)": value,
            "Share of pipeline": f"{round(100 * value / total_value, 1)}%",
            "Average deal (USD)": int(value / len(at_stage)) if at_stage else 0,
        })

    scope = region.value if region else "All regions"
    return MetricTable(
        name=f"Pipeline by stage - {scope}",
        description="Open opportunities distributed across pipeline stages.",
        columns=["Stage", "Opps", "Value (USD)", "Share of pipeline",
                 "Average deal (USD)"],
        rows=rows,
        notes=["Share is of total open pipeline value in scope."],
    )


def stalled_deals(conn: Connectors, region: Region | None = None,
                  limit: int = 15) -> MetricTable:
    """Open deals over 60 days old that did not change stage in the last week.

    Two conditions rather than one: an old deal that is still moving is
    healthy, and a young deal that has not moved is not yet a problem. It is
    the combination that signals something is stuck.
    """
    accounts = {a.id: a for a in conn.sfdc.list_accounts()}
    stalled = [o for o in conn.sfdc.list_opportunities(region) if o.is_stalled]
    stalled.sort(key=lambda o: o.amount_usd, reverse=True)

    rows = [{
        "Opportunity": o.name,
        "Account": accounts[o.account_id].name if o.account_id in accounts else "-",
        "Region": o.owner_region.value,
        "Stage": o.stage.value,
        "Amount (USD)": o.amount_usd,
        "Days open": o.days_in_pipeline,
    } for o in stalled[:limit]]

    return MetricTable(
        name="Stalled deals",
        description=(
            f"Open deals over 60 days old with no stage change in the past week. "
            f"{len(stalled)} found, showing the largest {min(limit, len(stalled))}."
        ),
        columns=["Opportunity", "Account", "Region", "Stage", "Amount (USD)",
                 "Days open"],
        rows=rows,
        notes=[
            f"Total value at risk: ${sum(o.amount_usd for o in stalled):,}.",
            "Stalled = open, older than 60 days, same stage as one week ago.",
        ],
    )


def stage_movement(conn: Connectors, region: Region | None = None) -> MetricTable:
    """Which deals advanced, slipped or held still in the past week."""
    opps = _open(conn.sfdc.list_opportunities(region))
    order = {stage: i for i, stage in enumerate(OPEN_STAGES)}

    advanced = held = slipped = 0
    advanced_value = 0
    for o in opps:
        if o.stage_one_week_ago is None:
            continue
        now = order.get(o.stage, -1)
        before = order.get(o.stage_one_week_ago, -1)
        if now > before:
            advanced += 1
            advanced_value += o.amount_usd
        elif now < before:
            slipped += 1
        else:
            held += 1

    total = advanced + held + slipped or 1
    rows = [
        {"Movement": "Advanced a stage", "Opps": advanced,
         "Share": f"{round(100 * advanced / total, 1)}%"},
        {"Movement": "No change", "Opps": held,
         "Share": f"{round(100 * held / total, 1)}%"},
        {"Movement": "Slipped back", "Opps": slipped,
         "Share": f"{round(100 * slipped / total, 1)}%"},
    ]

    scope = region.value if region else "All regions"
    return MetricTable(
        name=f"Week-over-week stage movement - {scope}",
        description="How open opportunities moved in the past week.",
        columns=["Movement", "Opps", "Share"],
        rows=rows,
        notes=[f"Value that advanced a stage: ${advanced_value:,}."],
    )


def pipeline_in_accounts(conn: Connectors, account_ids: list[str]) -> MetricTable:
    """Total open pipeline across a specific set of accounts.

    Used for "pipeline in the room" at an event, but deliberately generic so
    any caller with a list of accounts can reuse it.
    """
    accounts = {a.id: a for a in conn.sfdc.list_accounts()}
    wanted = set(account_ids)
    opps = [o for o in conn.sfdc.list_opportunities()
            if o.account_id in wanted and o.is_open]

    by_account: dict[str, list[Opportunity]] = {}
    for o in opps:
        by_account.setdefault(o.account_id, []).append(o)

    rows = []
    for account_id in account_ids:
        account = accounts.get(account_id)
        if account is None:
            continue
        account_opps = by_account.get(account_id, [])
        rows.append({
            "Account": account.name,
            "City": account.city,
            "Open opps": len(account_opps),
            "Open pipeline (USD)": sum(o.amount_usd for o in account_opps),
            "Furthest stage": max(
                (o.stage.value for o in account_opps), default="No open opp"),
            "Stalled": any(o.is_stalled for o in account_opps),
        })
    rows.sort(key=lambda r: r["Open pipeline (USD)"], reverse=True)

    total = sum(r["Open pipeline (USD)"] for r in rows)
    no_opp = [r["Account"] for r in rows if r["Open opps"] == 0]

    return MetricTable(
        name="Pipeline across selected accounts",
        description=f"Open pipeline for {len(rows)} accounts.",
        columns=["Account", "City", "Open opps", "Open pipeline (USD)",
                 "Furthest stage", "Stalled"],
        rows=rows,
        notes=[
            f"Total open pipeline: ${total:,}.",
            f"{len(no_opp)} of {len(rows)} accounts have no open opportunity"
            + (f": {', '.join(no_opp[:8])}." if no_opp else "."),
        ],
    )


def closed_won_rate(conn: Connectors, region: Region | None = None) -> float:
    """Won divided by all closed. A plain float for use inside other tables."""
    opps = conn.sfdc.list_opportunities(region)
    won = sum(1 for o in opps if o.stage == OppStage.CLOSED_WON)
    lost = sum(1 for o in opps if o.stage == OppStage.CLOSED_LOST)
    return round(won / (won + lost), 4) if (won + lost) else 0.0
