"""Load RevOps dummy tables from dummy_data/*.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DUMMY_DIR = Path(__file__).resolve().parents[2] / "dummy_data"

REVOPS_TABLES = (
    "account.json",
    "verbal_call_history.json",
    "conversion_rate_history.json",
    "needed_win_rate.json",
    "opportunity.json",
    "opportunity_contact_role.json",
    "email_log.json",
    "call_transcript.json",
    "pitch_view.json",
    "quote.json",
    "quote_line.json",
    "quote_pricing.json",
    "bundle.json",
    "bundle_sku.json",
    "sales_order.json",
    "invoice.json",
    "account_health.json",
    "pricing_analytics.json",
    "credit_arr.json",
    "forecast_meta.json",
    "forecast_gap.json",
    "forecast_participation.json",
    "kpi_cycle_days.json",
    "kpi_period.json",
)


def dummy_tables_ready() -> bool:
    return all((DUMMY_DIR / name).is_file() for name in REVOPS_TABLES)


def read_table(name: str) -> list[dict[str, Any]]:
    path = DUMMY_DIR / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{name} must be a JSON array")
    return payload


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(float(value))


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def load_accounts() -> list[dict[str, str]]:
    return [
        {
            "account": row["account"],
            "account_id": row["account_id"],
            "owner": row["owner"],
            "geo": row["geo"],
        }
        for row in read_table("account.json")
    ]


def load_verbal_calls() -> dict[str, dict[str, Any]]:
    return {
        row["rep_name"]: {
            "rep_id": row["rep_id"],
            "fiscal_week": row["fiscal_week"],
            "verbal_call_acv": _int(row["verbal_call_acv"]),
        }
        for row in read_table("verbal_call_history.json")
    }


def load_conversion_rates() -> dict[str, dict[str, Any]]:
    return {
        row["rep_name"]: {
            "historical_win_rate_ss40": _float(row["historical_win_rate_ss40"]),
        }
        for row in read_table("conversion_rate_history.json")
    }


def load_needed_win_rate() -> dict[str, float]:
    return {
        row["rep_name"]: _float(row["needed_win_rate_ss40"])
        for row in read_table("needed_win_rate.json")
    }


def load_opportunities() -> dict[str, dict[str, Any]]:
    return {
        row["opp_id"]: {
            "opp_id": row["opp_id"],
            "account": row["account"],
            "crm_health_score": _int(row["crm_health_score"]),
            "is_backup_deal": _bool(row["is_backup_deal"]),
            "backup_opp_id": row.get("backup_opp_id") or "",
            "stage_name": row["stage_name"],
            "stage_required_fields_complete_pct": _float(
                row["stage_required_fields_complete_pct"]
            ),
            "next_step": row["next_step"],
            "next_step_last_modified_date": row["next_step_last_modified_date"],
            "manager_notes": row["manager_notes"],
        }
        for row in read_table("opportunity.json")
    }


def load_contact_roles() -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {}
    for row in read_table("opportunity_contact_role.json"):
        roles.setdefault(row["account"], []).append(row["role_name"])
    return roles


def load_email_log() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "last_inbound_email_date": row["last_inbound_email_date"],
            "outbound_count_since_inbound": _int(row["outbound_count_since_inbound"]),
        }
        for row in read_table("email_log.json")
    }


def load_call_transcript() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {"last_call_date": row["last_call_date"]}
        for row in read_table("call_transcript.json")
    }


def load_pitch_view() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {"last_content_view_date": row["last_content_view_date"]}
        for row in read_table("pitch_view.json")
    }


def load_quote_ops() -> dict[str, dict[str, Any]]:
    return {
        row["quote_id"]: {
            "quote_id": row["quote_id"],
            "is_primary": _bool(row["is_primary"]),
            "forecast_value": _int(row["forecast_value"]),
            "discount_percentage": _float(row["discount_percentage"]),
            "has_deal_desk_validation_errors": _bool(
                row["has_deal_desk_validation_errors"]
            ),
            "validation_error_codes": _list(row["validation_error_codes"]),
            "modernization_carve_acv": _int(row["modernization_carve_acv"]),
            "carve_notes": row.get("carve_notes") or "",
            "has_special_terms": _bool(row["has_special_terms"]),
            "special_terms_notes": row.get("special_terms_notes") or "",
        }
        for row in read_table("quote.json")
    }


def load_quote_lines() -> dict[str, list[dict[str, Any]]]:
    lines: dict[str, list[dict[str, Any]]] = {}
    for row in read_table("quote_line.json"):
        lines.setdefault(row["quote_id"], []).append(
            {
                "sku_name": row["sku_name"],
                "is_agentic_attached": _bool(row["is_agentic_attached"]),
            }
        )
    return lines


def load_quote_pricing() -> list[dict[str, Any]]:
    return [
        {
            "quote_id": row["quote_id"],
            "opp_id": row["opp_id"],
            "account": row["account"],
            "list_price": _int(row["list_price"]),
            "quoted_price": _int(row["quoted_price"]),
            "floor_price": _int(row["floor_price"]),
            "bundle_id": row["bundle_id"],
            "errors": _list(row["errors"]),
        }
        for row in read_table("quote_pricing.json")
    ]


def load_bundles() -> dict[str, dict[str, Any]]:
    skus: dict[str, list[str]] = {}
    for row in read_table("bundle_sku.json"):
        skus.setdefault(row["bundle_id"], []).append(row["sku_name"])
    return {
        row["bundle_id"]: {
            "name": row["name"],
            "skus": skus.get(row["bundle_id"], []),
            "list_price": _int(row["list_price"]),
            "attach": _list(row["attach"]),
        }
        for row in read_table("bundle.json")
    }


def load_sales_orders() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "arr_amount": _int(row["arr_amount"]),
            "order_hygiene_status": row["order_hygiene_status"],
            "po_number": row.get("po_number") or "",
            "hold_reason": row.get("hold_reason") or "",
        }
        for row in read_table("sales_order.json")
    }


def load_invoices() -> dict[str, list[dict[str, Any]]]:
    invoices: dict[str, list[dict[str, Any]]] = {
        row["account"]: [] for row in read_table("account.json")
    }
    for row in read_table("invoice.json"):
        invoices.setdefault(row["account"], []).append(
            {
                "aging_category": row["aging_category"],
                "outstanding_balance": _int(row["outstanding_balance"]),
            }
        )
    return invoices


def load_account_health() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "health_score": _int(row["health_score"]),
            "churn_risk_arr": _int(row["churn_risk_arr"]),
            "csm_name": row.get("csm_name") or "",
        }
        for row in read_table("account_health.json")
    }


def load_pricing_ops() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "deal_score": _int(row["deal_score"]),
            "left_on_table_acv": _int(row["left_on_table_acv"]),
            "suggested_upsell_skus": _list(row["suggested_upsell_skus"]),
            "payment_structure_type": row["payment_structure_type"],
        }
        for row in read_table("pricing_analytics.json")
    }


def load_credit_arr() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "arr": _int(row["arr"]),
            "credit_limit": _int(row["credit_limit"]),
            "open_ar": _int(row["open_ar"]),
            "proposed_bookings": _int(row["proposed_bookings"]),
            "terms": row["terms"],
        }
        for row in read_table("credit_arr.json")
    }


def load_forecast_meta() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "category": row["category"],
            "commit": _int(row["commit"]),
            "upside": _int(row["upside"]),
            "slip_days": _int(row["slip_days"]),
            "note": row["note"],
        }
        for row in read_table("forecast_meta.json")
    }


def load_forecast_gaps() -> dict[str, list[str]]:
    gaps: dict[str, list[str]] = {
        row["account"]: [] for row in read_table("account.json")
    }
    for row in read_table("forecast_gap.json"):
        gaps.setdefault(row["account"], []).append(row["gap"])
    return gaps


def load_forecast_participation() -> dict[str, dict[str, Any]]:
    return {
        row["account"]: {
            "on_verbal_call": _bool(row["on_verbal_call"]),
            "last_forecast_call": row.get("last_forecast_call") or "",
            "missing_from_call": _bool(row["missing_from_call"]),
        }
        for row in read_table("forecast_participation.json")
    }


def load_kpi_cycle_days() -> dict[str, int]:
    return {
        row["account"]: _int(row["avg_sales_cycle_days"])
        for row in read_table("kpi_cycle_days.json")
    }


def load_kpi_periods() -> list[dict[str, Any]]:
    return [
        {
            "geo": str(row["geo"]).strip().lower(),
            "period": str(row["period"]).strip().lower(),
            "verbal_call_acv": _int(row["verbal_call_acv"]),
            "pipeline_coverage_ratio": _float(row["pipeline_coverage_ratio"]),
            "commit_acv": _int(row["commit_acv"]),
            "upside_acv": _int(row["upside_acv"]),
            "landing_projected": _int(row["landing_projected"]),
            "avg_sales_cycle_days": _int(row["avg_sales_cycle_days"]),
        }
        for row in read_table("kpi_period.json")
    ]
