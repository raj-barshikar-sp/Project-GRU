"""Deterministic specialist-to-synthesis payload construction."""

from __future__ import annotations

import json
from typing import Any

from agents.session_memory import SESSION_KEYS


def _public_name(agent_id: str) -> str:
    if agent_id.startswith("revops_"):
        return agent_id.removeprefix("revops_")
    return agent_id


def build_synthesis_request(
    *,
    user_query: str,
    state: Any,
    results: dict[str, Any],
    validation_errors: list[str] | None = None,
) -> str:
    """Serialize queried rows and specialist outputs without LLM paraphrasing."""
    verified_records: dict[str, Any] = {}
    specialist_results: dict[str, Any] = {}
    for agent_id, payload in results.items():
        name = _public_name(agent_id)
        if isinstance(payload, dict):
            records = payload.get("records") or {}
            if records:
                verified_records[name] = records
            specialist_results[name] = {
                key: value for key, value in payload.items() if key != "records"
            }
        else:
            specialist_results[name] = payload
    specialists = list(specialist_results)
    payload = {
        "original_question": user_query,
        "verified_records": verified_records,
        "working_context": {
            key: str(state.get(key) or "") for key in SESSION_KEYS
        },
        "specialist_results": specialist_results,
        "specialist": specialists[0] if len(specialists) == 1 else "",
        "specialists": specialists,
        "writing_guidance": (
            "Write markdown for the AE. Choose the structure that fits this "
            "specialist and question. Do not use a fixed Summary / Key Insights "
            "/ Recommended Actions / Artifacts template. Plain English. No "
            "field dumps. No raw validation codes."
            + (
                " KPI rows are complete. Zero is a real number. Quote weekly, "
                "monthly, and quarterly coverage, verbal call, landing, and cycle "
                "time from those rows. Never say metrics were missing or request "
                "a fresh pull."
                if any(
                    isinstance(records, dict) and records.get("KpiPeriod")
                    for records in verified_records.values()
                )
                else ""
            )
        ),
    }
    if validation_errors:
        payload["retry_instruction"] = (
            "Correct these contract violations while preserving grounded facts: "
            + "; ".join(validation_errors)
            + ". Rewrite in plain English from verified_records."
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
