"""Dummy datasets for RevOps entities, loaded from dummy_data/*.json."""

from __future__ import annotations

from typing import Any

from agents.data.crm import ACCOUNTS, OPPORTUNITIES
from agents.data.dummy_store import (
    load_account_health,
    load_call_transcript,
    load_contact_roles,
    load_conversion_rates,
    load_email_log,
    load_forecast_participation,
    load_invoices,
    load_kpi_cycle_days,
    load_kpi_periods,
    load_needed_win_rate,
    load_opportunities,
    load_pitch_view,
    load_pricing_ops,
    load_quote_lines,
    load_quote_ops,
    load_sales_orders,
    load_verbal_calls,
)
from agents.data.pillar import EXTRA_OPPORTUNITIES
from agents.data.revops import forecast_rollup

LARGE_DEAL = 500_000

VERBAL_CALLS = load_verbal_calls()
CONVERSION_RATES = load_conversion_rates()
NEEDED_WIN_RATE = load_needed_win_rate()
OPPORTUNITY_OPS = load_opportunities()
CONTACT_ROLES = load_contact_roles()
EMAIL_LOG = load_email_log()
CALL_TRANSCRIPT = load_call_transcript()
PITCH_VIEW = load_pitch_view()
QUOTE_OPS = load_quote_ops()
QUOTE_LINES = load_quote_lines()
SALES_ORDERS = load_sales_orders()
INVOICES = load_invoices()
ACCOUNT_HEALTH = load_account_health()
PRICING_OPS = load_pricing_ops()
KPI_CYCLE_DAYS = load_kpi_cycle_days()
KPI_PERIODS = load_kpi_periods()
FORECAST_PARTICIPATION = load_forecast_participation()

FISCAL_WEEK = next(iter(VERBAL_CALLS.values()))["fiscal_week"]

_PRIMARY_OPP = {
    name: records[0]["opp_id"] for name, records in OPPORTUNITIES.items()
}


def _money(value: int | float | None) -> str:
    if value is None:
        return "none"
    return f"${int(value):,}"


def _boats(accounts: list[str]) -> list[str]:
    return list(dict.fromkeys(str(ACCOUNTS[name]["owner"]) for name in accounts))


def _primary_opp(account: str) -> dict[str, Any]:
    return OPPORTUNITY_OPS[_PRIMARY_OPP[account]]


def _forecast_rollup_fields(accounts: list[str]) -> dict[str, int]:
    pack = forecast_rollup(accounts)
    commit = int(pack["commit_total"])
    return {
        "commit_rollup_acv": commit,
        "best_case_rollup_acv": commit + int(pack["upside_total"]),
    }


def _kpi_summary(accounts: list[str]) -> dict[str, Any]:
    verbal, _present, _when, boats = _verbal(accounts)
    rollup = _forecast_rollup_fields(accounts)
    cover = (
        round(rollup["best_case_rollup_acv"] / verbal, 2) if verbal else 0.0
    )
    landing = rollup["commit_rollup_acv"]
    cycle = (
        round(sum(KPI_CYCLE_DAYS[name] for name in accounts) / len(accounts))
        if accounts
        else 0
    )
    rates = [
        CONVERSION_RATES[boat]["historical_win_rate_ss40"]
        for boat in boats
        if boat in CONVERSION_RATES
    ]
    win = round(sum(rates) / len(rates), 1) if rates else 0.0
    return {
        "verbal_call_acv": verbal,
        "pipeline_coverage_ratio": cover,
        "quarterly_landing_projected": landing,
        "avg_sales_cycle_days": cycle,
        "historical_win_rate_ss40": win,
    }


def _backup(account: str) -> str:
    opp = _primary_opp(account)
    backup_id = opp.get("backup_opp_id") or ""
    if backup_id and backup_id in OPPORTUNITY_OPS:
        extra = next(
            (
                row
                for row in (EXTRA_OPPORTUNITIES.get(account) or [])
                if row["opp_id"] == backup_id
            ),
            None,
        )
        label = extra["name"] if extra else backup_id
        amount = int(extra["amount"]) if extra else 0
        return f"{backup_id} {label} ({_money(amount)})"
    return ""


def _verbal(accounts: list[str]) -> tuple[int, bool, str, list[str]]:
    boats = _boats(accounts)
    total = sum(int(VERBAL_CALLS[boat]["verbal_call_acv"]) for boat in boats)
    present = bool(boats)
    when = ", ".join(
        (
            f"{boat} {VERBAL_CALLS[boat]['rep_id']} "
            f"{VERBAL_CALLS[boat]['fiscal_week']} "
            f"{_money(VERBAL_CALLS[boat]['verbal_call_acv'])}"
        )
        for boat in boats
    )
    return total, present, when, boats


def _first_match(query: str, rules: list[tuple[str, tuple[str, ...]]]) -> str:
    lowered = query.lower()
    for topic, hints in rules:
        if any(hint in lowered for hint in hints if hint):
            return topic
    return ""
