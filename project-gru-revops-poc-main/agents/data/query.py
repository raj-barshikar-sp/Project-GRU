"""Query dummy entity tables. Returns records — the writer answers the question."""

from __future__ import annotations

from typing import Any

from agents.data.revops import (
    BUNDLES,
    credit_arr_calc,
    forecast_rollup,
    pricing_waterfall,
    qbr_deck,
    quotes_for,
    territory_for,
)
from agents.data.ops import (
    ACCOUNT_HEALTH,
    CALL_TRANSCRIPT,
    CONVERSION_RATES,
    CONTACT_ROLES,
    EMAIL_LOG,
    FORECAST_PARTICIPATION,
    INVOICES,
    KPI_PERIODS,
    NEEDED_WIN_RATE,
    OPPORTUNITY_OPS,
    PITCH_VIEW,
    PRICING_OPS,
    QUOTE_LINES,
    QUOTE_OPS,
    SALES_ORDERS,
    VERBAL_CALLS,
    _boats,
    _first_match,
    _forecast_rollup_fields,
    _kpi_summary,
    _primary_opp,
)


def query_verbal_call_history(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for boat in _boats(accounts):
        row = VERBAL_CALLS[boat]
        rows.append({"rep_name": boat, **row})
    return rows


def query_forecast_rollup(accounts: list[str]) -> dict[str, Any]:
    pack = forecast_rollup(accounts)
    fields = _forecast_rollup_fields(accounts)
    return {
        **fields,
        "accounts": accounts,
        "coverage": pack["coverage"],
        "upside_total": pack["upside_total"],
        "missing_data": pack["missing_data"],
        "risks": pack["risks"],
    }


def query_conversion_rate_history(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for boat in _boats(accounts):
        rows.append(
            {
                "rep_name": boat,
                **CONVERSION_RATES[boat],
                "needed_win_rate_ss40": NEEDED_WIN_RATE[boat],
            }
        )
    return rows


def query_opportunities(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in OPPORTUNITY_OPS.values()
        if row["account"] in accounts
    ]


def query_quotes(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for quote in quotes_for(accounts):
        ops = QUOTE_OPS[quote["quote_id"]]
        rows.append(
            {
                **ops,
                "account": quote["account"],
                "list_price": quote["list_price"],
                "quoted_price": quote["quoted_price"],
                "floor_price": quote["floor_price"],
                "discount_pct": quote["discount_pct"],
                "vs_floor": quote["vs_floor"],
                "below_floor": quote["below_floor"],
                "quote_errors": quote["errors"],
                "bundle_id": quote["bundle_id"],
                "stage_name": _primary_opp(quote["account"])["stage_name"],
            }
        )
    return rows


def query_quote_lines(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for quote in query_quotes(accounts):
        for line in QUOTE_LINES.get(quote["quote_id"], []):
            rows.append({"quote_id": quote["quote_id"], "account": quote["account"], **line})
    return rows


def query_contact_roles(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        {"account": name, "role_name": role}
        for name in accounts
        for role in CONTACT_ROLES.get(name, [])
    ]


def query_email_log(accounts: list[str]) -> list[dict[str, Any]]:
    return [{"account": name, **EMAIL_LOG[name]} for name in accounts if name in EMAIL_LOG]


def query_call_transcript(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        {"account": name, **CALL_TRANSCRIPT[name]}
        for name in accounts
        if name in CALL_TRANSCRIPT
    ]


def query_pitch_view(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        {"account": name, **PITCH_VIEW[name]} for name in accounts if name in PITCH_VIEW
    ]


def query_forecast_participation(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        {"account": name, **FORECAST_PARTICIPATION[name]}
        for name in accounts
        if name in FORECAST_PARTICIPATION
    ]


def query_kpi_summary(accounts: list[str]) -> dict[str, Any]:
    return _kpi_summary(accounts)


def query_kpi_periods(accounts: list[str]) -> list[dict[str, Any]]:
    geos = {territory_for(name) for name in accounts} - {""}
    return [dict(row) for row in KPI_PERIODS if row["geo"] in geos]


def query_sales_orders(accounts: list[str]) -> list[dict[str, Any]]:
    return [{"account": name, **SALES_ORDERS[name]} for name in accounts if name in SALES_ORDERS]


def query_invoices(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in accounts:
        for invoice in INVOICES.get(name, []):
            rows.append({"account": name, **invoice})
    return rows


def query_account_health(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        {"account": name, **ACCOUNT_HEALTH[name]}
        for name in accounts
        if name in ACCOUNT_HEALTH
    ]


def query_pricing_analytics(accounts: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in accounts:
        pack = pricing_waterfall(name)
        rows.append(
            {
                "account": name,
                "sku": pack["sku"],
                "below_floor": pack["below_floor"],
                "peer_band": pack["peer_band"],
                "waterfall": pack["steps"],
                **PRICING_OPS[name],
            }
        )
    return rows


def inspect_forecast(query: str, accounts: list[str]) -> dict[str, Any]:
    pack = forecast_rollup(accounts)
    boats = _boats(accounts)
    records = {
        "VerbalCallHistory": query_verbal_call_history(accounts),
        "ForecastRollup": query_forecast_rollup(accounts),
        "ConversionRateHistory": query_conversion_rate_history(accounts),
        "Opportunity": query_opportunities(accounts),
    }
    topic = _first_match(
        query,
        [
            ("match", ("roll-up", "rollup", "match my deal", "match the deal")),
            ("verbal", ("rev intel", "verbal call")),
            ("cover", ("pipeline cover", "cover to my call")),
            ("backup", ("backup", "large deal")),
            ("crm_score", ("crm score", "crm_health")),
            ("pacing", ("pacing", "conversion")),
            ("weekly", ("weekly update", "manager note", "next step")),
            ("rollup", ("regional forecast", "forecast risk", "missing forecast")),
        ],
    ) or "rollup"
    return {
        "topic": topic,
        "records": records,
        "findings": [],
        "next_action": "",
        "owner": boats[0] if boats else "",
        "artifact_title": "",
        "artifact_body": "",
        "commit_total": pack["commit_total"],
        "upside_total": pack["upside_total"],
        "coverage": pack["coverage"],
        "missing_data": pack["missing_data"],
        "risks": pack["risks"],
        "accounts": [row["account"] for row in pack["accounts"]],
        "copy_ready": [],
    }


def inspect_quoting(query: str, accounts: list[str]) -> dict[str, Any]:
    quotes = query_quotes(accounts)
    lines = query_quote_lines(accounts)
    topic = _first_match(
        query,
        [
            ("forecast_value", ("forecast value",)),
            ("ss20", ("ss20", "by ss20")),
            ("ss40", ("ss40", "primary quote")),
            ("deal_desk", ("deal desk", "missing")),
            ("deviation", ("deviation", "pricing deviation")),
            ("errors", ("errors in quotes", "quote errors", "validate errors")),
            ("carve", ("carve",)),
            ("agentic", ("agentic",)),
            ("terms", ("special terms",)),
            ("deep_dive", ("deep dive", "flag a")),
            ("bundles", ("bundle",)),
        ],
    ) or ""
    bundles = [
        f"{row['account']} {BUNDLES[row['bundle_id']]['name']}: "
        + ", ".join(BUNDLES[row["bundle_id"]]["skus"])
        for row in quotes
    ]
    return {
        "topic": topic,
        "records": {
            "Quote": quotes,
            "QuoteLine": lines,
            "Opportunity": query_opportunities(accounts),
            "AccountHealth": query_account_health(accounts),
            "EmailLog": query_email_log(accounts),
            "ContactRole": query_contact_roles(accounts),
        },
        "findings": [],
        "next_action": "",
        "quotes": [f"{row['quote_id']} {row['account']}" for row in quotes],
        "deviations": [
            (
                f"{row['quote_id']} {row['account']}: quoted ${row['quoted_price']:,} "
                f"is {row['discount_percentage']}% off list, vs_floor {row['vs_floor']}."
            )
            for row in quotes
        ],
        "errors": [
            f"{row['quote_id']} {row['account']}: {code}"
            for row in quotes
            for code in row["validation_error_codes"]
        ],
        "bundles": bundles,
        "copy_ready": [],
        "artifact_title": "",
        "artifact_body": "",
    }


def inspect_reporting(query: str, accounts: list[str]) -> dict[str, Any]:
    topic = _first_match(
        query,
        [
            ("forecast_review", ("forecast review",)),
            ("pipeline_review", ("pipeline review",)),
            ("qa", ("q&a", "q and a", "question of key")),
            ("deck", ("turn these", "monthly/quarterly", "quarterly deck", "monthly deck")),
            ("kpis", ("kpi", "key metric", "key kpis")),
            ("qbr", ("qbr",)),
        ],
    ) or "qbr"
    kpis = query_kpi_summary(accounts)
    target = accounts[0] if accounts else ""
    slides = (
        [f"{slide['title']}: {slide['body']}" for slide in qbr_deck(target)]
        if target
        else []
    )
    quotes = quotes_for(accounts)
    return {
        "topic": topic,
        "report_type": topic,
        "records": {
            "KpiSummary": kpis,
            "KpiPeriod": query_kpi_periods(accounts),
            "ConversionRateHistory": query_conversion_rate_history(accounts),
            "ForecastRollup": query_forecast_rollup(accounts),
            "Quote": [
                {
                    "quote_id": row["quote_id"],
                    "account": row["account"],
                    "quoted_price": row["quoted_price"],
                    "below_floor": row["below_floor"],
                }
                for row in quotes
            ],
        },
        "findings": [],
        "next_action": "",
        "slides": slides,
        "copy_ready": [],
        "artifact_title": "",
        "artifact_body": "",
    }


def inspect_hygiene(query: str, accounts: list[str]) -> dict[str, Any]:
    topic = _first_match(
        query,
        [
            ("inspect", ("inspect", "what we expect", "expect")),
            ("participation", ("participation",)),
            ("notes", ("updated notes", "notes")),
            ("deal", ("deal hygiene", "completed fields", "per stage")),
        ],
    ) or "deal"
    opps = query_opportunities(accounts)
    gaps = [
        (
            f"{row['account']} {row['opp_id']} {row['stage_name']}: "
            f"stage_required_fields_complete_pct={row['stage_required_fields_complete_pct']}"
        )
        for row in opps
        if row["stage_required_fields_complete_pct"] < 90
    ]
    return {
        "topic": topic,
        "records": {
            "Opportunity": opps,
            "OpportunityContactRole": query_contact_roles(accounts),
            "EmailLog": query_email_log(accounts),
            "CallTranscript": query_call_transcript(accounts),
            "PitchView": query_pitch_view(accounts),
            "ForecastParticipation": query_forecast_participation(accounts),
        },
        "findings": [],
        "next_action": "",
        "gaps": gaps,
        "copy_ready": [],
        "artifact_title": "",
        "artifact_body": "",
        "accounts": accounts,
    }


def inspect_otc(query: str, accounts: list[str]) -> dict[str, Any]:
    rows = [credit_arr_calc(account) for account in accounts]
    topic = _first_match(
        query,
        [
            ("orders", ("order review", "order hygiene")),
            ("aging", ("aging", "receivable")),
            ("churn", ("churn", "csm")),
            ("credit", ("credit", "arr calculator", "arr")),
        ],
    ) or "credit"
    holds = [
        f"{row['account']} HOLD: headroom ${row['headroom']:,} on {row['terms']}"
        for row in rows
        if row["hold"]
    ]
    lines = [
        (
            f"{row['account']}: ARR ${row['arr']:,}, limit ${row['credit_limit']:,}, "
            f"AR ${row['open_ar']:,}, proposed ${row['proposed_bookings']:,}, "
            f"headroom ${row['headroom']:,}"
        )
        for row in rows
    ]
    return {
        "topic": topic,
        "records": {
            "SalesOrder": query_sales_orders(accounts),
            "Invoice": query_invoices(accounts),
            "AccountHealth": query_account_health(accounts),
            "CreditArr": rows,
        },
        "findings": [],
        "next_action": "",
        "accounts": accounts,
        "arr_total": sum(row["arr"] for row in rows),
        "headroom_total": sum(row["headroom"] for row in rows),
        "holds": holds,
        "lines": lines,
        "copy_ready": [],
        "artifact_title": "",
        "artifact_body": "",
    }


def inspect_pricing(query: str, accounts: list[str]) -> dict[str, Any]:
    topic = _first_match(
        query,
        [
            ("score", ("deal score", "leaving on the table", "left on the table")),
            ("architect", ("deal architect", "maximizing", "architect", "upsell")),
            ("levers", ("revenue lever", "deal structure", "levers", "payment_structure")),
        ],
    ) or "waterfall"
    analytics = query_pricing_analytics(accounts)
    first = analytics[0] if analytics else {}
    waterfall = [
        f"{step['step']}: ${step['amount']:,}"
        for step in (first.get("waterfall") or [])
    ]
    return {
        "topic": topic,
        "records": {"PricingAnalytics": analytics},
        "findings": [],
        "next_action": "",
        "account": first.get("account") or "",
        "sku": first.get("sku") or "",
        "waterfall": waterfall,
        "below_floor": bool(first.get("below_floor")),
        "peer_band": first.get("peer_band") or "",
        "copy_ready": [],
        "artifact_title": "",
        "artifact_body": "",
    }
