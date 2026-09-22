"""Task menu, filter catalogs, and prompt composition for the AE workspace."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
import re

from agents.data.crm import ACCOUNTS, TERRITORIES
from agents.data.dummy_store import dummy_tables_ready, load_accounts, load_opportunities

TASK_MENU: tuple[dict, ...] = (
    {
        "id": "forecasting",
        "label": "Forecasting",
        "items": (
            {
                "id": "verbal_call",
                "label": "Weekly verbal call in Rev Intel",
                "scoped_prompt": "Pull the weekly verbal call in Rev Intel for {territory} and flag any missing week or ACV gap.",
            },
            {
                "id": "call_vs_rollup",
                "label": "Verbal call vs deal roll-up",
                "scoped_prompt": "Compare the verbal call to the CRM deal roll-up for {territory} and call out any mismatch.",
            },
            {
                "id": "pipeline_cover",
                "label": "Pipeline cover to call",
                "scoped_prompt": "What is pipeline cover to the verbal call for {territory}, and is coverage healthy?",
            },
            {
                "id": "large_deal_backup",
                "label": "Large-deal backup",
                "scoped_prompt": "For large deals in {territory}, do I have a backup opportunity, and which deals are uncovered?",
            },
            {
                "id": "crm_score",
                "label": "CRM score this quarter",
                "scoped_prompt": "What is the CRM score for deals this quarter for {account}, and which deals look weak?",
            },
            {
                "id": "pacing",
                "label": "Pacing vs conversion",
                "scoped_prompt": "Am I pacing to the verbal call based on conversion rates for {territory}?",
            },
            {
                "id": "weekly_update",
                "label": "Weekly update",
                "scoped_prompt": "Do I have a weekly update (next step and manager note) for {account}, and which deals are stale?",
            },
        ),
    },
    {
        "id": "quoting",
        "label": "Quoting",
        "items": (
            {
                "id": "forecast_value",
                "label": "Forecast value on the quote",
                "scoped_prompt": "Review forecast value on quotes for {account} and list any quote missing a number.",
            },
            {
                "id": "ss20",
                "label": "Quote by SS20",
                "scoped_prompt": "Check that {account} has a quote by SS20 — if not, what is blocking it?",
            },
            {
                "id": "ss40",
                "label": "Primary quote at SS40",
                "scoped_prompt": "Confirm a primary quote at SS40 for {account} and note any gap.",
            },
            {
                "id": "deal_desk",
                "label": "Deal desk rules",
                "scoped_prompt": "Check deal desk rules for {account} — if we do not match, what is missing?",
            },
            {
                "id": "pricing_deviation",
                "label": "Quote pricing deviations",
                "scoped_prompt": "Analyze quote pricing deviations versus floor for {account}.",
            },
            {
                "id": "quote_errors",
                "label": "Validate errors in quotes",
                "scoped_prompt": "Validate errors in quotes for {account} and explain each issue in plain English.",
            },
            {
                "id": "carve",
                "label": "Carve notes for modernizations",
                "scoped_prompt": "Review carve or carve notes for modernizations on {account}.",
            },
            {
                "id": "agentic",
                "label": "Agentic attached",
                "scoped_prompt": "Check whether agentic is attached on {account} and which SKUs are missing it.",
            },
            {
                "id": "special_terms",
                "label": "Special terms",
                "scoped_prompt": "Flag special terms on {account} and whether deal desk has notes.",
            },
            {
                "id": "deep_dive",
                "label": "Flag a deep dive",
                "scoped_prompt": "Should I flag a deep dive review for {account}, and why?",
            },
        ),
    },
    {
        "id": "reporting",
        "label": "Reporting",
        "items": (
            {
                "id": "kpis",
                "label": "Weekly / monthly / quarterly KPIs",
                "scoped_prompt": "Show weekly, monthly, and quarterly key KPIs for {territory} — coverage, verbal call, landing, and cycle time.",
            },
            {
                "id": "kpi_decks",
                "label": "Turn KPIs into decks",
                "scoped_prompt": "Turn the key KPIs into monthly and quarterly decks for {territory}.",
            },
            {
                "id": "forecast_review",
                "label": "Forecast review deck",
                "scoped_prompt": "Prepare a forecast review pack for {territory} with commit, upside, and gaps.",
            },
            {
                "id": "pipeline_review",
                "label": "Pipeline review",
                "scoped_prompt": "Prepare a pipeline review pack for {territory}, including coverage and stalled deals.",
            },
            {
                "id": "metrics_qa",
                "label": "Q&A of key metrics",
                "scoped_prompt": "Q&A on key metrics for {territory} — verbal call, coverage, win rate, and cycle time.",
            },
            {
                "id": "qbr_deck",
                "label": "QBR deck",
                "scoped_prompt": "Prepare a QBR deck for {account} with the latest forecast, hygiene, and next steps.",
            },
        ),
    },
    {
        "id": "hygiene",
        "label": "Hygiene",
        "items": (
            {
                "id": "inspect_expect",
                "label": "Inspect what we expect",
                "scoped_prompt": "Inspect what we expect on {account} — missing roles, notes, and next steps.",
            },
            {
                "id": "participation",
                "label": "Participation",
                "scoped_prompt": "Check forecast participation for {territory} and who is missing from the call.",
            },
            {
                "id": "deal_hygiene",
                "label": "Deal hygiene",
                "scoped_prompt": "Deal hygiene — completed fields per stage for {account}, and what is still blank.",
            },
            {
                "id": "updated_notes",
                "label": "Updated notes",
                "scoped_prompt": "Do I have updated notes for {account}, and which opportunities went quiet?",
            },
        ),
    },
    {
        "id": "otc",
        "label": "OTC",
        "items": (
            {
                "id": "credit_arr",
                "label": "Credit and ARR calculator",
                "scoped_prompt": "Calculate credit and ARR for {account}, including limit, open AR, and proposed bookings.",
            },
            {
                "id": "order_review",
                "label": "Order review and hygiene",
                "scoped_prompt": "Order review and hygiene for {account} — holds, missing PO, and ARR.",
            },
            {
                "id": "aging_ar",
                "label": "Aging receivables",
                "scoped_prompt": "Show aging receivables for {account} by bucket and outstanding balance.",
            },
            {
                "id": "churn_csm",
                "label": "Churn impact (CSM)",
                "scoped_prompt": "What is the churn impact and tie to CSM for {account}?",
            },
        ),
    },
    {
        "id": "pricing_analytics",
        "label": "Pricing analytics",
        "items": (
            {
                "id": "deal_score",
                "label": "Deal score / money left on the table",
                "scoped_prompt": "What is the deal score and what are we leaving on the table for {account}?",
            },
            {
                "id": "deal_architect",
                "label": "Deal architect",
                "scoped_prompt": "Deal architect — maximizing revenue and return for {account}, with the pricing levers to use.",
            },
            {
                "id": "revenue_levers",
                "label": "Revenue levers",
                "scoped_prompt": "What revenue levers are available based on deal structure for {account}?",
            },
        ),
    },
)

GROUP_AGENT = {
    "forecasting": "revops_forecast",
    "quoting": "revops_quoting",
    "reporting": "revops_reporting",
    "hygiene": "revops_hygiene",
    "otc": "revops_otc",
    "pricing_analytics": "revops_pricing",
}

_STAGE_CODE = re.compile(r"ss\d{2}", re.IGNORECASE)


def _default_territory() -> str:
    counts: dict[str, int] = {}
    for row in load_accounts():
        geo = str(row.get("geo") or "").strip().lower()
        if geo:
            counts[geo] = counts.get(geo, 0) + 1
    if not counts:
        return ""
    return sorted(counts, key=lambda geo: (-counts[geo], geo))[0]


def _default_account_for_task(item: dict) -> str:
    blob = f"{item.get('id', '')} {item.get('scoped_prompt', '')}"
    stages = [match.upper() for match in _STAGE_CODE.findall(blob)]
    if stages:
        want = stages[0]
        opps = sorted(
            load_opportunities().values(), key=lambda row: str(row.get("opp_id") or "")
        )
        for opp in opps:
            if str(opp.get("stage_name") or "").upper() == want:
                return str(opp.get("account") or "")
    geo = _default_territory()
    for row in load_accounts():
        if str(row.get("geo") or "").strip().lower() == geo:
            return str(row.get("account") or "")
    rows = load_accounts()
    return str(rows[0]["account"]) if rows else ""


def _geo_for_account(account: str) -> str:
    for row in load_accounts():
        if row.get("account") == account:
            return str(row.get("geo") or "").strip().lower()
    return ""


def fill_task_prompt(
    item: dict, *, account: str = "", territory: str = ""
) -> str:
    """Fill a scoped template from dummy accounts/geos, not baked names."""
    template = str(item.get("scoped_prompt") or "")
    account = account or _default_account_for_task(item)
    territory = territory or _geo_for_account(account) or _default_territory()
    return template.format(account=account, territory=territory)


REPORT_TYPES: tuple[dict[str, str], ...] = (
    {"id": "qbr", "label": "QBR deck"},
    {"id": "forecast_review", "label": "Forecast review"},
    {"id": "pipeline_review", "label": "Pipeline review"},
    {"id": "kpis", "label": "Weekly / monthly / quarterly KPIs"},
)

_TASK_FILTER_OVERRIDES = {
    "large_deal_backup": ("geo", "boat", "opp"),
}

_TASK_REPORT_IDS = {
    "kpis": ("kpis",),
    "kpi_decks": ("kpis",),
    "forecast_review": ("forecast_review",),
    "pipeline_review": ("pipeline_review",),
    "metrics_qa": ("kpis",),
    "qbr_deck": ("qbr",),
}


def _item_filter_meta(group_id: str, item: dict) -> dict:
    """Geo/boat for territory work, opps for accounts, report types for decks."""
    names = _TASK_FILTER_OVERRIDES.get(item["id"])
    if names is None:
        names = ["geo", "boat"]
        if "{account}" in str(item.get("scoped_prompt") or ""):
            names.append("opp")
        if group_id == "reporting":
            names.append("report")
        names = tuple(dict.fromkeys(names))
    meta = {"filters": list(names)}
    if group_id == "reporting" and item["id"] in _TASK_REPORT_IDS:
        meta["report_ids"] = list(_TASK_REPORT_IDS[item["id"]])
    return meta


def _catalog_item(group_id: str, item: dict) -> dict:
    filled = {**dict(item), **_item_filter_meta(group_id, item)}
    filled["default_prompt"] = fill_task_prompt(item)
    return filled


_TASKS_BY_ID = {
    item["id"]: _catalog_item(group["id"], item)
    for group in TASK_MENU
    for item in group["items"]
}


@dataclass
class FilterSelection:
    geos: list[str] = field(default_factory=list)
    boats: list[str] = field(default_factory=list)
    opps: list[str] = field(default_factory=list)
    report_types: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    windows: list[str] = field(default_factory=list)


def _territory_for_account(account: str) -> str:
    for territory, names in TERRITORIES.items():
        if territory != "all" and account in names:
            return territory
    return ""


def _ui_features() -> dict[str, bool]:
    flag = os.getenv("SELLER_COPILOT_UI_REASONING", "1").strip().lower()
    return {"reasoning": flag not in ("0", "false", "no")}


def workspace_catalog() -> dict:
    """Return tasks and filters that have a working agent and dummy JSON rows."""
    assistant = {
        "name": "Bob",
        "title": "Bob the Back Office Minion",
        "tagline": "Forecast, quote, and report without leaving this pane.",
    }
    ui = _ui_features()
    if not dummy_tables_ready():
        return {
            "assistant": assistant,
            "tasks": [],
            "filters": {
                "geos": [],
                "boats": [],
                "opps": [],
                "report_types": [],
                "sizes": [],
                "stages": [],
                "windows": [],
            },
            "ui": ui,
        }
    accounts = load_accounts()
    geos = [
        {"id": geo, "label": f"Geo: {geo.title()}"}
        for geo in dict.fromkeys(
            str(row["geo"]).strip().lower()
            for row in accounts
            if str(row.get("geo") or "").strip()
        )
    ]
    boats = sorted({row["owner"] for row in accounts if row.get("owner")})
    owner_of = {row["account"]: row["owner"] for row in accounts}
    geo_of = {row["account"]: row["geo"] for row in accounts}
    opps = [
        {
            "id": row["opp_id"],
            "account": row["account"],
            "territory": geo_of.get(row["account"], ""),
            "owner": owner_of.get(row["account"], ""),
            "label": f"{row['opp_id']} · {row['account']} · {row['stage_name']}",
        }
        for row in load_opportunities().values()
    ]
    extra = {"sizes": [], "stages": [], "windows": []}
    if dummy_tables_ready():
        from ui.dashboard import dashboard_filter_catalog

        extra = dashboard_filter_catalog()
    return {
        "assistant": assistant,
        "tasks": [
            {
                "id": group["id"],
                "label": group["label"],
                "agent": GROUP_AGENT[group["id"]],
                "items": [_catalog_item(group["id"], item) for item in group["items"]],
            }
            for group in TASK_MENU
            if group["id"] in GROUP_AGENT
        ],
        "filters": {
            "geos": geos,
            "boats": [{"id": name, "label": f"Boat: {name}"} for name in boats],
            "opps": opps,
            "report_types": [dict(item) for item in REPORT_TYPES],
            **extra,
        },
        "ui": ui,
    }


def _opp_index() -> dict[str, dict[str, str]]:
    catalog = workspace_catalog()
    return {item["id"]: item for item in catalog["filters"]["opps"]}


def _first_account(selection: FilterSelection) -> str:
    opps = _opp_index()
    for opp_id in selection.opps:
        if opp_id in opps:
            return opps[opp_id]["account"]
    for geo in selection.geos:
        names = TERRITORIES.get(geo, [])
        if names:
            return names[0]
    for boat in selection.boats:
        for account, record in ACCOUNTS.items():
            if record.get("owner") == boat:
                return account
    return ""


def _first_territory(selection: FilterSelection, account: str) -> str:
    if selection.geos:
        return selection.geos[0]
    return _territory_for_account(account) or _default_territory()


def restrict_filters(task_id: str, selection: FilterSelection) -> FilterSelection:
    """Drop filter values that do not apply to the selected task."""
    task = _TASKS_BY_ID.get(task_id)
    if task is None:
        return selection
    names = set(task.get("filters") or ())
    if not names:
        return selection
    allowed_reports = set(task.get("report_ids") or [])
    reports = list(selection.report_types)
    if "report" not in names:
        reports = []
    elif allowed_reports:
        reports = [item for item in reports if item in allowed_reports]
    return FilterSelection(
        geos=list(selection.geos) if "geo" in names else [],
        boats=list(selection.boats) if "boat" in names else [],
        opps=list(selection.opps) if "opp" in names else [],
        report_types=reports,
        sizes=list(selection.sizes),
        stages=list(selection.stages),
        windows=list(selection.windows),
    )


def compose_task_message(
    task_id: str, selection: FilterSelection | None = None
) -> str:
    """Turn a left-nav task plus right-rail filters into one AE prompt."""
    task = _TASKS_BY_ID.get(task_id)
    if task is None:
        raise KeyError(task_id)
    selection = restrict_filters(task_id, selection or FilterSelection())
    account = _first_account(selection) or _default_account_for_task(task)
    territory = _first_territory(selection, account)
    text = str(task.get("scoped_prompt") or "").format(
        account=account, territory=territory
    )
    return apply_filter_notes(text, selection)


def filter_notes(selection: FilterSelection) -> list[str]:
    notes: list[str] = []
    if selection.geos:
        notes.append("Geos: " + ", ".join(selection.geos))
    if selection.boats:
        notes.append("Boats: " + ", ".join(selection.boats))
    if selection.opps:
        labels = [
            _opp_index()[opp_id]["label"]
            for opp_id in selection.opps
            if opp_id in _opp_index()
        ]
        if labels:
            notes.append("Rep opps: " + "; ".join(labels))
    if selection.report_types:
        labels = [
            item["label"]
            for item in REPORT_TYPES
            if item["id"] in selection.report_types
        ]
        if labels:
            notes.append("Reporting types: " + ", ".join(labels))
    if selection.sizes:
        notes.append("Opp size: " + ", ".join(selection.sizes))
    if selection.stages:
        notes.append("SS stage: " + ", ".join(selection.stages))
    if selection.windows:
        notes.append("Time: " + ", ".join(selection.windows))
    return notes


def apply_filter_notes(text: str, selection: FilterSelection | None) -> str:
    notes = filter_notes(selection or FilterSelection())
    if not notes:
        return text
    return text + "\n\nWorking filters:\n" + "\n".join(f"- {note}" for note in notes)


def default_starters() -> list[str]:
    return [fill_task_prompt(item) for group in TASK_MENU for item in group["items"]]
