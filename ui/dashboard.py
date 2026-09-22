"""Dummy connectors and dashboard payload: opps, tasks, Slack, notifications."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from agents.data.dummy_store import load_accounts, load_opportunities, load_quote_pricing
from ui.catalog import TASK_MENU

SIZE_FILTERS = (
    {"id": "smb", "label": "Under $500k", "min": 0, "max": 499_999},
    {"id": "mid", "label": "$500k–$1.5M", "min": 500_000, "max": 1_499_999},
    {"id": "enterprise", "label": "$1.5M+", "min": 1_500_000, "max": None},
)
STAGE_FILTERS = (
    {"id": "SS20", "label": "SS20"},
    {"id": "SS40", "label": "SS40"},
    {"id": "SS50", "label": "SS50"},
    {"id": "SS60", "label": "SS60"},
)
TIME_FILTERS = (
    {"id": "this_week", "label": "Close this week"},
    {"id": "this_month", "label": "Close this month"},
    {"id": "this_quarter", "label": "Close this quarter"},
    {"id": "stale", "label": "Stale next step (30d+)"},
)

# Dummy Salesforce overlay — close dates for the live book.
_CLOSE_DATES = {
    "OPP-711": "2026-09-22",
    "OPP-712": "2026-10-18",
    "OPP-241": "2026-09-28",
    "OPP-242": "2026-11-12",
    "OPP-318": "2026-09-19",
    "OPP-402": "2026-12-04",
    "OPP-570": "2026-09-25",
    "OPP-611": "2026-10-08",
    "OPP-788": "2026-09-30",
}

_DUMMY_ARTIFACTS = (
    {
        "id": "art-q241",
        "kind": "email",
        "title": "Q-241 Acme Corp — sendable email",
        "account": "Acme Corp",
        "created": "2026-09-16T15:40:00Z",
        "source": "chat",
        "body": (
            "Subject: Acme Corp – Quote-to-Cash & Dayton Sandbox Next Steps\n\n"
            "Hi Helen,\n\nI hope you are having a great week.\n\n"
            "I am following up on our proposal for the Acme Corp Quote-to-Cash, "
            "Oracle connector, and Capped Professional Services deployment "
            "for the Dayton plant.\n\n"
            "We are currently targeting a total investment of $640,000.\n\n"
            "Best regards,\n"
        ),
    },
    {
        "id": "art-west-kpis",
        "kind": "talking_points",
        "title": "West KPI snapshot",
        "account": "NovaPay",
        "created": "2026-09-15T18:12:00Z",
        "source": "chat",
        "body": "West coverage 1.8x. Verbal call $2.1M. Landing $0 this week is a real number.",
    },
)


def _parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _size_id(amount: int) -> str:
    for bucket in SIZE_FILTERS:
        ceiling = bucket["max"]
        if amount >= int(bucket["min"]) and (ceiling is None or amount <= int(ceiling)):
            return str(bucket["id"])
    return "enterprise"


def _quarter(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3 + 1


def _in_time_window(opp: dict[str, Any], window: str, today: date) -> bool:
    close = _parse_day(str(opp["close_date"]))
    touched = _parse_day(str(opp["last_touch"]))
    if window == "this_week":
        start = today - timedelta(days=today.weekday())
        return start <= close < start + timedelta(days=7)
    if window == "this_month":
        return close.year == today.year and close.month == today.month
    if window == "this_quarter":
        return _quarter(close) == _quarter(today)
    if window == "stale":
        return (today - touched).days >= 30
    return True


def _book_opps() -> list[dict[str, Any]]:
    quotes = {row["opp_id"]: row for row in load_quote_pricing()}
    accounts = {row["account"]: row for row in load_accounts()}
    rows: list[dict[str, Any]] = []
    for opp in load_opportunities().values():
        quote = quotes.get(opp["opp_id"]) or {}
        account = accounts.get(opp["account"]) or {}
        amount = int(quote.get("quoted_price") or 0)
        close = _CLOSE_DATES.get(opp["opp_id"], "2026-12-31")
        last_touch = str(opp.get("next_step_last_modified_date") or "")[:10]
        rows.append(
            {
                "id": opp["opp_id"],
                "account": opp["account"],
                "stage": str(opp.get("stage_name") or ""),
                "amount": amount,
                "size": _size_id(amount),
                "geo": str(account.get("geo") or ""),
                "owner": str(account.get("owner") or ""),
                "health": int(opp.get("crm_health_score") or 0),
                "complete_pct": float(opp.get("stage_required_fields_complete_pct") or 0),
                "next_step": str(opp.get("next_step") or ""),
                "last_touch": last_touch or close,
                "close_date": close,
                "backup": bool(opp.get("is_backup_deal")),
                "errors": list(quote.get("errors") or []),
            }
        )
    return rows


def _slack_work() -> list[dict[str, Any]]:
    """Dummy Slack connector: only messages tagged as work."""
    return [
        {
            "id": "sl-1",
            "channel": "#acme-dayton",
            "from": "Helen Cho",
            "when": "Today 9:14",
            "text": "Can we lock a Dayton sandbox date this week? Plant finance is free Thursday.",
            "work": True,
            "account": "Acme Corp",
        },
        {
            "id": "sl-2",
            "channel": "#west-forecast",
            "from": "Avery Cole",
            "when": "Today 8:02",
            "text": "West verbal call still missing NovaPay landing. Flagging for Friday.",
            "work": True,
            "account": "NovaPay",
        },
        {
            "id": "sl-3",
            "channel": "#deal-desk",
            "from": "Casey Nguyen",
            "when": "Yesterday",
            "text": "Meridian BAA walkthrough is on calendar. Need nursing informatics pack attached.",
            "work": True,
            "account": "Meridian Health",
        },
        {
            "id": "sl-4",
            "channel": "#random",
            "from": "Sam Rivera",
            "when": "Yesterday",
            "text": "Who is grabbing lunch after the all-hands?",
            "work": False,
            "account": "",
        },
    ]


def _notifications(opps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for opp in opps:
        for error in opp["errors"]:
            notes.append(
                {
                    "id": f"nt-{opp['id']}-err",
                    "kind": "task",
                    "title": f"{opp['id']} needs a quote fix",
                    "detail": error,
                    "account": opp["account"],
                    "due": "Today",
                }
            )
        if opp["complete_pct"] < 60:
            notes.append(
                {
                    "id": f"nt-{opp['id']}-hygiene",
                    "kind": "task",
                    "title": f"{opp['account']} hygiene is thin",
                    "detail": f"{opp['complete_pct']:g}% of {opp['stage']} required fields are complete.",
                    "account": opp["account"],
                    "due": "This week",
                }
            )
    notes.append(
        {
            "id": "nt-forecast-friday",
            "kind": "task",
            "title": "Weekly verbal call pack",
            "detail": "West + central books are due before Friday forecast.",
            "account": "",
            "due": "Fri",
        }
    )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for note in notes:
        if note["id"] in seen:
            continue
        seen.add(note["id"])
        unique.append(note)
    return unique[:8]


def _format_due(when: datetime, today: date) -> str:
    clock = f"{when.hour}:{when.minute:02d}"
    if when.date() == today:
        return f"Today {clock}"
    if when.date() == today + timedelta(days=1):
        return f"Tomorrow {clock}"
    return f"{when.strftime('%a')} {clock}"


def _task_bar(today: date | None = None) -> list[dict[str, Any]]:
    day = today or date.today()
    picks = (
        ("quoting", "quote_errors", 0, time(8, 15), "Acme Corp"),
        ("hygiene", "deal_hygiene", 0, time(9, 40), "NovaPay"),
        ("forecasting", "verbal_call", 1, time(9, 0), "west"),
        ("quoting", "ss20", 2, time(10, 30), "Helix Robotics"),
        ("reporting", "kpis", 4, time(14, 0), "west"),
        ("otc", "credit_arr", 4, time(16, 20), "Acme Corp"),
    )
    by_id = {
        item["id"]: (group["id"], group["label"], item)
        for group in TASK_MENU
        for item in group["items"]
    }
    rows: list[dict[str, Any]] = []
    for group_id, item_id, offset, clock, scope in picks:
        packed = by_id.get(item_id)
        if not packed:
            continue
        _gid, group_label, item = packed
        when = datetime.combine(day + timedelta(days=offset), clock)
        rows.append(
            {
                "id": item_id,
                "group": group_label,
                "group_id": group_id,
                "label": item["label"],
                "due": _format_due(when, day),
                "due_at": when.isoformat(timespec="minutes"),
                "scope": scope,
            }
        )
    rows.sort(key=lambda row: row["due_at"])
    return rows


def _match(
    opp: dict[str, Any],
    *,
    geos: list[str],
    boats: list[str],
    opps: list[str],
    sizes: list[str],
    stages: list[str],
    windows: list[str],
    today: date,
) -> bool:
    if geos and opp["geo"] not in geos:
        return False
    if boats and opp["owner"] not in boats:
        return False
    if opps and opp["id"] not in opps:
        return False
    if sizes and opp["size"] not in sizes:
        return False
    if stages and opp["stage"] not in stages:
        return False
    if windows and not any(_in_time_window(opp, window, today) for window in windows):
        return False
    return True


def dashboard_payload(
    *,
    geos: list[str] | None = None,
    boats: list[str] | None = None,
    opps: list[str] | None = None,
    sizes: list[str] | None = None,
    stages: list[str] | None = None,
    windows: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Filter dummy Salesforce + Slack connectors into one AE dashboard."""
    today = today or date.today()
    geos = [item for item in (geos or []) if item]
    boats = [item for item in (boats or []) if item]
    opps = [item for item in (opps or []) if item]
    sizes = [item for item in (sizes or []) if item]
    stages = [item for item in (stages or []) if item]
    windows = [item for item in (windows or []) if item]
    book = _book_opps()
    visible = [
        row
        for row in book
        if _match(
            row,
            geos=geos,
            boats=boats,
            opps=opps,
            sizes=sizes,
            stages=stages,
            windows=windows,
            today=today,
        )
    ]
    by_stage: dict[str, dict[str, Any]] = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in STAGE_FILTERS
    }
    by_size: dict[str, dict[str, Any]] = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in SIZE_FILTERS
    }
    for row in visible:
        stage = by_stage.get(row["stage"])
        if stage:
            stage["count"] += 1
            stage["amount"] += row["amount"]
        size = by_size.get(row["size"])
        if size:
            size["count"] += 1
            size["amount"] += row["amount"]
    slack = [item for item in _slack_work() if item["work"]]
    if geos or boats or opps or sizes or stages:
        slack = [
            item
            for item in slack
            if not item["account"]
            or any(row["account"] == item["account"] for row in visible)
        ]
    pipeline = sum(row["amount"] for row in visible if not row["backup"])
    return {
        "as_of": today.isoformat(),
        "filters": {
            "sizes": [dict(item) for item in SIZE_FILTERS],
            "stages": [dict(item) for item in STAGE_FILTERS],
            "windows": [dict(item) for item in TIME_FILTERS],
        },
        "copy": {
            "kicker": "SailPoint · RevOps",
            "title": "Pipeline",
            "kpi_pipeline": "Pipeline",
            "kpi_pipeline_hint": "Click to clear size & stage",
            "kpi_open": "Open opps",
            "kpi_open_hint": "Jump to the book",
            "kpi_week": "Close this week",
            "kpi_week_hint": "Click to filter this week",
            "kpi_week_filter": "this_week",
            "kpi_slack": "Work Slack",
            "kpi_slack_hint": "Open the Slack feed",
            "empty": "No opportunities match these filters.",
            "unit": "opps",
            "table": "Opportunities",
            "stage_chart": "Pipeline by stage",
            "size_chart": "Mix by opp size",
            "filter_size": "Opp size",
            "filter_stage": "SS stage",
            "filter_time": "Time",
            "filter_geo": "Geo",
            "col_id": "Opp",
            "col_name": "Account",
            "col_stage": "Stage",
            "col_size": "Size",
            "col_amount": "Amount",
            "col_close": "Close",
            "col_health": "Health",
        },
        "kpis": {
            "pipeline": pipeline,
            "open_opps": len([row for row in visible if not row["backup"]]),
            "closing_week": len(
                [row for row in visible if _in_time_window(row, "this_week", today)]
            ),
            "slack_work": len(slack),
        },
        "by_stage": list(by_stage.values()),
        "by_size": list(by_size.values()),
        "opps": visible,
        "tasks": _task_bar(today),
        "notifications": _notifications(visible),
        "slack": slack,
        "artifacts": [dict(item) for item in _DUMMY_ARTIFACTS],
        "connectors": [
            {"id": "salesforce", "label": "Salesforce", "status": "connected"},
            {"id": "slack", "label": "Slack", "status": "connected"},
            {"id": "chat", "label": "Chat artifacts", "status": "local"},
        ],
    }


def dashboard_filter_catalog() -> dict[str, list[dict[str, str]]]:
    return {
        "sizes": [{"id": item["id"], "label": item["label"]} for item in SIZE_FILTERS],
        "stages": [{"id": item["id"], "label": item["label"]} for item in STAGE_FILTERS],
        "windows": [{"id": item["id"], "label": item["label"]} for item in TIME_FILTERS],
    }
