"""ABM account scoring and tiering.

Composite score = weighted sum of firmographic fit, intent strength,
engagement depth and pipeline status. Every number an agent quotes about
account priority comes from here.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable, Region


def _firmographic_score(icp: dict, industry: str, employees: int,
                        is_target: bool) -> int:
    weights = icp.get("industry_weights", {})
    industry_pts = weights.get(industry, 40)
    size_pts = 0
    lo = icp.get("min_employee_count", 0)
    hi = icp.get("max_employee_count", 100_000)
    if lo <= employees <= hi:
        size_pts = 100
    elif employees < lo:
        size_pts = max(20, int(100 * employees / lo))
    else:
        size_pts = max(40, int(100 * hi / employees))
    target_pts = 100 if is_target else 50
    return int((industry_pts + size_pts + target_pts) / 3)


def _intent_score(signals: list) -> int:
    if not signals:
        return 0
    scores = [s.intent_score for s in signals]
    trending = sum(1 for s in signals if s.trending)
    base = int(sum(scores) / len(scores))
    return min(100, base + min(10, trending * 3))


def _engagement_score(events: list) -> int:
    if not events:
        return 0
    # More touchpoints = warmer account, capped at 100.
    return min(100, 20 + len(events) * 12)


def _pipeline_score(has_open_opp: bool, open_value: int) -> int:
    if has_open_opp:
        return min(100, 60 + open_value // 500_000)
    return 30  # whitespace opportunity


def account_tiering(conn: Connectors, region: Region | None = None,
                    limit: int = 25) -> MetricTable:
    """Rank accounts by ICP fit, intent, engagement and pipeline status."""
    icp = conn.kb.get_icp()
    weights = icp.get("weights", {
        "firmographic": 0.35, "intent": 0.35,
        "engagement": 0.15, "pipeline": 0.15,
    })
    thresholds = icp.get("tier_thresholds", {"Tier 1": 72, "Tier 2": 52})

    accounts = conn.sfdc.list_accounts(region)
    signals_by_account: dict[str, list] = {}
    for sig in conn.sixsense.list_intent_signals():
        signals_by_account.setdefault(sig.account_id, []).append(sig)

    engagement_by_account: dict[str, list] = {}
    for ev in conn.marketo.list_engagement_events():
        engagement_by_account.setdefault(ev.account_id, []).append(ev)

    opps = conn.sfdc.list_opportunities(region)
    open_by_account: dict[str, int] = {}
    for o in opps:
        if o.is_open:
            open_by_account[o.account_id] = (
                open_by_account.get(o.account_id, 0) + o.amount_usd
            )

    rows = []
    for acct in accounts:
        firm = _firmographic_score(
            icp, acct.industry, acct.employee_count, acct.is_target_account)
        intent = _intent_score(signals_by_account.get(acct.id, []))
        engage = _engagement_score(engagement_by_account.get(acct.id, []))
        pipe = _pipeline_score(
            acct.id in open_by_account, open_by_account.get(acct.id, 0))
        composite = int(
            firm * weights.get("firmographic", 0.35)
            + intent * weights.get("intent", 0.35)
            + engage * weights.get("engagement", 0.15)
            + pipe * weights.get("pipeline", 0.15)
        )
        if composite >= thresholds.get("Tier 1", 72):
            tier = "Tier 1"
        elif composite >= thresholds.get("Tier 2", 52):
            tier = "Tier 2"
        else:
            tier = "Tier 3"

        top_kw = sorted(
            signals_by_account.get(acct.id, []),
            key=lambda s: s.intent_score, reverse=True,
        )
        kw = top_kw[0].keyword if top_kw else "-"

        rows.append({
            "Account": acct.name,
            "Account id": acct.id,
            "City": acct.city,
            "Region": acct.region.value,
            "Industry": acct.industry,
            "Composite score": composite,
            "Tier": tier,
            "Top intent": kw,
            "Open pipeline (USD)": open_by_account.get(acct.id, 0),
            "Target account": acct.is_target_account,
        })

    rows.sort(key=lambda r: r["Composite score"], reverse=True)
    rows = rows[:limit]

    scope = region.value if region else "All regions"
    return MetricTable(
        name=f"ABM account tiering - {scope}",
        description=(
            f"Top {len(rows)} accounts ranked by composite ABM score."
        ),
        columns=["Account", "Account id", "City", "Region", "Industry",
                 "Composite score", "Tier", "Top intent",
                 "Open pipeline (USD)", "Target account"],
        rows=rows,
        notes=[
            "Composite = firmographic (35%) + intent (35%) + engagement (15%) "
            "+ pipeline (15%).",
            f"Tier 1 >= {thresholds.get('Tier 1', 72)}, "
            f"Tier 2 >= {thresholds.get('Tier 2', 52)}.",
            "Munich/Frankfurt target accounts with Zero Trust intent should "
            "rank highly.",
        ],
    )
