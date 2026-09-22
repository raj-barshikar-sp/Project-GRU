"""RevOps report packs from mock forecast and quote data."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import (
    forecast_rollup,
    qbr_deck,
    quotes_for,
    resolve_scope,
)
from agents.data.query import inspect_reporting
from agents.tooling import error, success
from agents.tooling import tool

_REPORTS = {
    "qbr": "qbr",
    "qbr deck": "qbr",
    "forecast_review": "forecast_review",
    "forecast review": "forecast_review",
    "pipeline_review": "pipeline_review",
    "pipeline review": "pipeline_review",
    "meeting_brief": "qbr",
    "call_recap": "qbr",
    "kpis": "kpis",
    "kpi": "kpis",
    "key kpis": "kpis",
    "key kpi": "kpis",
    "key metrics": "kpis",
    "weekly": "kpis",
    "monthly": "kpis",
    "quarterly": "kpis",
    "qa": "kpis",
    "q&a": "kpis",
    "deck": "kpis",
}


def _normalize_report_type(report_type: str) -> str:
    raw = report_type.strip().lower()
    if raw in _REPORTS:
        return _REPORTS[raw]
    if any(
        token in raw
        for token in ("kpi", "key metric", "weekly", "monthly", "quarterly", "q&a", "q and a")
    ):
        return "kpis"
    if "forecast review" in raw or "forecast_review" in raw:
        return "forecast_review"
    if "pipeline" in raw:
        return "pipeline_review"
    if "qbr" in raw:
        return "qbr"
    return ""


def _kpi_pack(accounts: list[str]) -> dict[str, Any]:
    pack = inspect_reporting("Show weekly, monthly, and quarterly key KPIs", accounts)
    kpis = pack["records"]["KpiSummary"]
    periods = pack["records"].get("KpiPeriod") or []
    names = ", ".join(accounts) or "the selected book"
    slides = [f"Weekly / monthly / quarterly KPIs for {names}."]
    for row in periods:
        slides.append(
            f"{row['period'].title()}: coverage {row['pipeline_coverage_ratio']}x, "
            f"call ${row['verbal_call_acv']:,}, commit ${row['commit_acv']:,}, "
            f"upside ${row['upside_acv']:,}, landing ${row['landing_projected']:,}, "
            f"cycle {row['avg_sales_cycle_days']} days."
        )
    if not periods:
        slides.extend(
            [
                f"Pipeline coverage ratio: {kpis['pipeline_coverage_ratio']}",
                f"Verbal call: ${kpis['verbal_call_acv']:,}",
                f"Quarterly landing projected: ${kpis['quarterly_landing_projected']:,}",
                f"Average sales cycle: {kpis['avg_sales_cycle_days']} days",
                f"Win rate at SS40: {kpis['historical_win_rate_ss40']}%",
            ]
        )
    elif kpis.get("historical_win_rate_ss40"):
        slides.append(f"Win rate: {kpis['historical_win_rate_ss40']}% at SS40.")
    copy = [
        f"{names}: coverage {kpis['pipeline_coverage_ratio']}x, "
        f"verbal ${kpis['verbal_call_acv']:,}, "
        f"quarterly landing ${kpis['quarterly_landing_projected']:,}, "
        f"cycle {kpis['avg_sales_cycle_days']} days, "
        f"win rate {kpis['historical_win_rate_ss40']}%."
    ]
    copy.extend(
        f"{row['period'].title()}: coverage {row['pipeline_coverage_ratio']}x, "
        f"call ${row['verbal_call_acv']:,}, landing ${row['landing_projected']:,}, "
        f"cycle {row['avg_sales_cycle_days']} days."
        for row in periods
    )
    return {
        "report_type": "kpis",
        "slides": slides,
        "records": pack["records"],
        "copy_ready": copy,
        "topic": "kpis",
    }


@tool
async def build_revops_pack(
    report_type: str = "qbr",
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """Build a QBR deck, forecast review, pipeline review, or KPI pack.

    Args:
        report_type: qbr, forecast_review, pipeline_review, or kpis.
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    kind = _normalize_report_type(report_type)
    if not kind:
        return error("Report type must be qbr, forecast_review, pipeline_review, or kpis.")
    accounts, err = resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id
    )
    if err:
        return err
    if kind == "kpis":
        if not accounts:
            return error("KPI pack needs an account, opp, geo, or boat.")
        return success(_kpi_pack(accounts))
    if kind == "qbr":
        target = accounts[0] if accounts else ""
        if not target:
            return error("QBR deck needs an account, opp, geo, or boat.")
        slides = [
            f"{slide['title']}: {slide['body']}" for slide in qbr_deck(target)
        ]
        copy = [qbr_deck(target)[0]["body"]]
        return success({"report_type": "qbr", "slides": slides, "copy_ready": copy})

    pack = forecast_rollup(accounts)
    if kind == "forecast_review":
        slides = [
            f"Coverage: {pack['coverage']} accounts",
            f"Commit ${pack['commit_total']:,} / upside ${pack['upside_total']:,}",
            *pack["missing_data"][:6],
            *pack["risks"][:6],
        ]
        copy = [
            f"Forecast review: commit ${pack['commit_total']:,}, "
            f"upside ${pack['upside_total']:,}."
        ]
        return success(
            {"report_type": "forecast_review", "slides": slides, "copy_ready": copy}
        )

    quotes = quotes_for(accounts)
    slides = [
        f"{row['account']} {row['quote_id']} ${row['quoted_price']:,} "
        f"({'below floor' if row['below_floor'] else 'above floor'})"
        for row in quotes
    ] or pack["missing_data"]
    copy = [f"Pipeline review: {len(accounts)} accounts in scope."]
    return success(
        {"report_type": "pipeline_review", "slides": slides, "copy_ready": copy}
    )
