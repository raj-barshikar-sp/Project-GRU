"""Load the JSON snapshots each specialist is allowed to read."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from agents.orchestrator.prompt import TASK_AGENT_IDS

DATA_DIR = Path(__file__).resolve().parents[1] / "new_dummy_data"

SOURCES_BY_AGENT = {
    "crm_intelligence_specialist": (
        "salesforce.json",
        "confluence_kb.json",
    ),
    "activity_engagement_specialist": (
        "salesforce.json",
        "gong_rev_intel.json",
        "calendar_email_activity.json",
    ),
    "rep_performance_specialist": (
        "salesforce.json",
        "gong_rev_intel.json",
        "workday_hr.json",
    ),
    "forecast_modeling_specialist": (
        "salesforce.json",
        "gong_rev_intel.json",
        "confluence_kb.json",
    ),
    "knowledge_base_rag": ("confluence_kb.json",),
}


def _salesforce_summary(payload: str) -> str:
    data = json.loads(payload)
    quarters: dict[str, dict[str, object]] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in data["opportunities"]:
        grouped[str(row["Fiscal_Quarter__c"])].append(row)
    for quarter, rows in grouped.items():
        categories: dict[str, dict[str, int]] = {}
        by_category: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_category[str(row["ForecastCategoryName"])].append(row)
        for category, category_rows in by_category.items():
            categories[category] = {
                "deal_count": len(category_rows),
                "acv_total": int(sum(row["ACV__c"] for row in category_rows)),
            }
        quarters[quarter] = {
            "deal_count": len(rows),
            "acv_total": int(sum(row["ACV__c"] for row in rows)),
            "by_forecast_category": categories,
        }
    return json.dumps(
        {
            "current_fiscal_quarter": data["dataset_metadata"][
                "current_fiscal_quarter"
            ],
            "all_opportunities": {
                "deal_count": len(data["opportunities"]),
                "acv_total": int(
                    sum(row["ACV__c"] for row in data["opportunities"])
                ),
            },
            "quarters": quarters,
        },
        indent=2,
    )


def source_context(agent_id: str) -> str:
    """Return current raw snapshots for one specialist."""
    if agent_id not in TASK_AGENT_IDS:
        raise KeyError(agent_id)
    blocks = []
    for name in SOURCES_BY_AGENT[agent_id]:
        payload = (DATA_DIR / name).read_text(encoding="utf-8")
        blocks.append(
            f"<data_source name=\"{name}\">\n"
            f"{payload}\n"
            "</data_source>"
        )
        if name == "salesforce.json":
            blocks.append(
                "<authoritative_summary source=\"salesforce.json\">\n"
                f"{_salesforce_summary(payload)}\n"
                "</authoritative_summary>"
            )
    return "\n\n".join(blocks)
