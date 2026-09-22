"""Normalized access to the consolidated v2 dummy snapshots."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "new_dummy_data"
FILES = (
    "salesforce.json",
    "gong_rev_intel.json",
    "calendar_email_activity.json",
    "workday_hr.json",
    "confluence_kb.json",
)


@lru_cache(maxsize=None)
def _read(name: str) -> dict[str, Any]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def data_ready() -> bool:
    return all((DATA_DIR / name).is_file() for name in FILES)


def salesforce() -> dict[str, Any]:
    return _read("salesforce.json")


def gong() -> dict[str, Any]:
    return _read("gong_rev_intel.json")


def activity() -> dict[str, Any]:
    return _read("calendar_email_activity.json")


def workday() -> dict[str, Any]:
    return _read("workday_hr.json")


def confluence() -> dict[str, Any]:
    return _read("confluence_kb.json")


def snapshot_time() -> str:
    return str(salesforce()["dataset_metadata"]["synced_at"])


def opportunities() -> list[dict[str, Any]]:
    return list(salesforce()["opportunities"])


def opportunity_by_id() -> dict[str, dict[str, Any]]:
    return {row["Id"]: row for row in opportunities()}


def manager_id() -> str:
    users = salesforce()["users"]
    managed_ids = {row.get("ManagerId") for row in users if row.get("ManagerId")}
    return next(
        (
            row["Id"]
            for row in users
            if row["Id"] in managed_ids and row.get("IsActive")
        ),
        "",
    )


def sales_users() -> list[dict[str, Any]]:
    scoped_manager = manager_id()
    return [
        row
        for row in salesforce()["users"]
        if row.get("ManagerId") == scoped_manager and row.get("IsActive")
    ]


def users_by_id() -> dict[str, dict[str, Any]]:
    return {row["Id"]: row for row in salesforce()["users"]}


def account_name(opportunity: dict[str, Any]) -> str:
    """Derive the account label because the extract has no account dimension."""
    return str(opportunity["Name"]).split(" - ", 1)[0].strip()


def normalized_opportunities() -> list[dict[str, Any]]:
    users = users_by_id()
    return [
        {
            **row,
            "Account_Name": account_name(row),
            "Owner_Name": users.get(row["OwnerId"], {}).get("Name", row["OwnerId"]),
        }
        for row in opportunities()
    ]


def accounts() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for opportunity in normalized_opportunities():
        name = opportunity["Account_Name"]
        result.setdefault(
            name,
            {
                "account_id": opportunity["AccountId"],
                "legal_name": name,
                "aliases": [],
                "owner": opportunity["Owner_Name"],
                "owner_id": opportunity["OwnerId"],
                "boat": opportunity.get("Boat__c", ""),
            },
        )
    return result


def territories() -> dict[str, list[str]]:
    names = list(accounts())
    return {"all": names, "east": names}


def list_accounts() -> list[str]:
    return list(accounts())


def resolve_account(value: str) -> str | None:
    needle = value.strip().lower()
    if not needle:
        return None
    exact = [name for name in accounts() if name.lower() == needle]
    if exact:
        return exact[0]
    partial = [name for name in accounts() if needle in name.lower()]
    return partial[0] if len(partial) == 1 else None


def normalized_calendar_events() -> list[dict[str, Any]]:
    return [
        {**row, "opportunity_id": row["deal_id"]}
        for row in activity()["calendar_events"]
    ]


def normalized_email_threads() -> list[dict[str, Any]]:
    return [
        {**row, "opportunity_id": row["deal_id"]}
        for row in activity()["email_threads"]
    ]


def normalized_deal_intelligence() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "opportunity_id": row["deal_id"],
            "risk_indicators": list(row.get("risk_signals") or []),
        }
        for row in gong()["deal_intelligence"]
    ]


def verbal_forecast_calls() -> list[dict[str, Any]]:
    return list(gong()["weekly_verbal_forecast_calls"])


def employee_by_sfdc_id() -> dict[str, dict[str, Any]]:
    return {
        row["sfdc_user_id"]: row
        for row in workday()["employees"]
        if row.get("sfdc_user_id")
    }


def productivity_tier_by_rep() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for tier in workday()["productivity_minima_benchmarks"]["tenure_tiers"]:
        for rep_id in tier["applicable_reps"]:
            result[rep_id] = tier
    return result


def stage_gate_document() -> dict[str, Any]:
    return next(
        row for row in confluence()["documents"] if row["id"] == "CONF-DOC-005"
    )


def stage_rules() -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for row in stage_gate_document()["content"]["stage_definitions_and_exit_gates"]:
        code = str(row["stage"]).split(" ", 1)[0]
        rules[code] = {
            "stage": row["stage"],
            "required_evidence_fields": list(row["required_evidence_fields"]),
            "exit_criteria": row["exit_criteria"],
            "max_stagnation_threshold_days": row[
                "max_stagnation_threshold_days"
            ],
        }
    return rules


def quarterly_quotas() -> dict[str, dict[str, Any]]:
    return {
        row["fiscal_quarter"]: row for row in salesforce()["quarterly_team_quotas"]
    }
