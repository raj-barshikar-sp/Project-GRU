"""Map internal child authors to AE-facing status copy."""

from __future__ import annotations

STATUS_BY_AUTHOR = {
    "route_planner": "Figuring out what you need…",
    "forecast_orchestrator": "Handing this to forecasting…",
    "quoting_orchestrator": "Handing this to quoting…",
    "reporting_orchestrator": "Handing this to reporting…",
    "hygiene_orchestrator": "Handing this to hygiene…",
    "otc_orchestrator": "Handing this to order-to-cash…",
    "pricing_orchestrator": "Handing this to pricing…",
    "revops_forecast": "Rolling up the forecast…",
    "revops_quoting": "Checking quotes…",
    "revops_reporting": "Building the RevOps pack…",
    "revops_hygiene": "Checking deal hygiene…",
    "revops_otc": "Calculating credit and ARR…",
    "revops_pricing": "Running pricing analytics…",
    "synthesis": "Summarizing what I found…",
}


def status_for_author(author: str) -> str | None:
    """Return a progress label, or None when the author is not shown to the AE."""
    return STATUS_BY_AUTHOR.get(author)
