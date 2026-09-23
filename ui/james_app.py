"""James (Marketing) adapter for the shared GRU browser shell.

Mirrors the thin Stuart/Henry adapters: it exposes ``/api/workspace`` and a
streaming ``/api/chat`` backed by the marketing orchestrator, and maps the
marketing filter catalog onto the shell's seven fixed filter buckets.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from calendar import monthrange
from collections.abc import AsyncIterator
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from mktg_core.connectors import get_connectors
from mktg_core.connectors._fixtures import load
from mktg_core.contracts.crm import AS_OF
from mktg_core.metrics.pipeline import coverage_by_region
from mktg_core.progress import THINKING_LABEL, status_for_author
from mktg_core.workspace import (
    FilterSelection,
    apply_filter_notes,
    apply_write_facts,
    compose_task_message,
    task_id_from_message,
    workspace_catalog as marketing_catalog,
)

from ui.attachments import decode_attachments, prompt_and_inline
from ui.briefing import parse_reply
from ui.stream import word_deltas

APP_NAME = "marketing-agents"
USER_ID = "marketer"
# The marketing repo lives beside the root shell; its .env carries Gemini keys.
MARKETING_ROOT = Path(__file__).resolve().parent.parent / "GRU-Marketing"
RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)
log = logging.getLogger("james.ui")

# The shell speaks in seven fixed filter buckets. Marketing dimensions are
# folded onto them here; item labels keep their marketing names so the rail
# still reads as campaigns, events, and accounts.
CATEGORY_TO_SHELL = {
    "campaigns": "boat",
    "campaign_types": "report",
    "asset_types": "size",
    "content": "stage",
    "events": "time",
    "accounts": "opp",
}


class ChatFilters(BaseModel):
    geos: list[str] = Field(default_factory=list)
    boats: list[str] = Field(default_factory=list)
    opps: list[str] = Field(default_factory=list)
    report_types: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    windows: list[str] = Field(default_factory=list)


class ChatAttachment(BaseModel):
    filename: str = ""
    mime_type: str = ""
    content_base64: str = ""


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = ""
    task_id: str = ""
    filters: ChatFilters | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


def _selection(filters: ChatFilters | None) -> FilterSelection:
    """Fold the shell's buckets back into the marketing selection."""
    if filters is None:
        return FilterSelection()
    return FilterSelection(
        geos=list(filters.geos),
        campaigns=list(filters.boats),
        campaign_types=list(filters.report_types),
        asset_types=list(filters.sizes),
        content=list(filters.stages),
        events=list(filters.windows),
        accounts=list(filters.opps),
    )


def _plain(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"id": item["id"], "label": item["label"]} for item in items]


def _task_shell_filters(item: dict[str, Any]) -> list[str]:
    policy = item.get("filter_policy") or {}
    names: list[str] = []
    for category in policy.get("categories", ()):
        shell = CATEGORY_TO_SHELL.get(category)
        if shell and shell not in names:
            names.append(shell)
    return names


def workspace_catalog() -> dict[str, Any]:
    """Marketing catalog, remapped onto the shared shell's contract."""
    catalog = marketing_catalog()
    filters = catalog.get("filters", {})
    accounts = filters.get("accounts", [])
    tasks = [
        {
            "id": group["id"],
            "label": group["label"],
            "agent": group.get("agent", ""),
            "items": [
                {
                    "id": item["id"],
                    "label": item["label"],
                    # Placeholder-free prompts: the shell only resolves
                    # {account}/{territory}, so hand it the clean default and
                    # let /api/chat recompose the scoped prompt from filters.
                    "default_prompt": item["default_prompt"],
                    "scoped_prompt": item["default_prompt"],
                    "filters": _task_shell_filters(item),
                }
                for item in group["items"]
            ],
        }
        for group in catalog.get("tasks", [])
    ]
    return {
        "assistant": {
            "name": "James",
            "title": "James the Marketing Assistant",
            "tagline": catalog.get("assistant", {}).get(
                "tagline", "Design, build, and analyze marketing from one workspace."
            ),
        },
        "tasks": tasks,
        "filters": {
            "geos": _plain(filters.get("geos", [])),
            "boats": _plain(filters.get("campaigns", [])),
            "opps": [
                {
                    "id": account["id"],
                    "account": account["label"],
                    "territory": account.get("region", ""),
                    "owner": "",
                    "label": account["label"],
                }
                for account in accounts
            ],
            "report_types": _plain(filters.get("campaign_types", [])),
            "sizes": _plain(filters.get("asset_types", [])),
            "stages": _plain(filters.get("content", [])),
            "windows": _plain(filters.get("events", [])),
        },
        "ui": catalog.get("ui", {"reasoning": True}),
    }


def _compose_message(body: ChatRequest, selection: FilterSelection) -> str:
    """Build the model prompt from the draft, task, and ticked filters."""
    message = body.message.strip()
    task_id = body.task_id.strip() or task_id_from_message(message)
    # An unedited task draft (empty, or exactly the default prompt) is rebuilt
    # from the filters; an edited draft is respected and only annotated.
    if task_id and (not message or task_id_from_message(message) == task_id):
        message = compose_task_message(task_id, selection)
    message = apply_filter_notes(message, selection)
    message = apply_write_facts(message, task_id or None, selection)
    return message


def _event_text(event: Event, *, thoughts: bool = False) -> str:
    parts = (event.content.parts if event.content else None) or []
    return "\n".join(
        part.text
        for part in parts
        if getattr(part, "text", None)
        and bool(getattr(part, "thought", False)) is thoughts
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Marketing dashboard
#
# The standalone GRU-Marketing repo shipped a rich campaign dashboard. When
# James moved onto the shared four-role shell the endpoint was dropped, so the
# marketing dashboard rendered empty. This restores the marketing campaign book
# and folds it onto the shell's fixed dashboard contract (the same one Bob,
# Stuart, and Henry emit): copy, filters, kpis, by_stage, by_size, opps, tasks,
# notifications, slack. Campaign dimensions are mapped onto the shell buckets:
#   stage <- campaign type, size <- spend band, amount <- spend.
# ---------------------------------------------------------------------------

# Spend bands a demand-gen manager actually uses.
SPEND_FILTERS = (
    {"id": "smb", "label": "Under $25k", "min": 0, "max": 24_999},
    {"id": "mid", "label": "$25k–$75k", "min": 25_000, "max": 74_999},
    {"id": "enterprise", "label": "$75k+", "min": 75_000, "max": None},
)
TIME_FILTERS = (
    {"id": "this_week", "label": "Ends this week"},
    {"id": "this_month", "label": "Ends this month"},
    {"id": "this_quarter", "label": "Ends this quarter"},
    {"id": "stale", "label": "Ended 30d+ ago"},
)
TYPE_SHORT = {
    "Paid Social": "Paid social",
    "Paid Search": "Paid search",
    "Content Syndication": "Syndication",
    "Field Event": "Field",
    "Email Nurture": "Nurture",
    "Tradeshow": "Tradeshow",
    "Webinar": "Webinar",
}
TYPE_ORDER = (
    "Webinar",
    "Field Event",
    "Paid Search",
    "Paid Social",
    "Content Syndication",
    "Email Nurture",
    "Tradeshow",
)
# Fixture campaigns all ended 4 Oct. Spread the book so time filters and
# "ending this week" are usable for marketers, without rewriting CRM maths.
BOOK_ENDS = {
    "CMP-001": date(2026, 10, 31),
    "CMP-002": date(2026, 9, 18),
    "CMP-003": date(2026, 9, 30),
    "CMP-004": date(2026, 9, 6),
    "CMP-005": date(2026, 9, 5),
    "CMP-006": date(2026, 12, 15),
    "CMP-007": date(2026, 6, 12),
    "CMP-008": date(2026, 9, 4),
    "CMP-009": date(2026, 9, 22),
    "CMP-010": date(2026, 8, 1),
    "CMP-011": date(2026, 9, 25),
    "CMP-012": date(2026, 11, 5),
}
SLACK_CHANNELS = {
    "LinkedIn": "#social-listening",
    "X": "#social-listening",
    "Reddit": "#demand-gen",
    "YouTube": "#content",
}

# Task bar: representative marketing jobs, keyed to real catalog task ids so the
# cards deep-link into chat correctly.
_TASK_PICKS = (
    ("campaign_performance", 0, time(8, 30), "this quarter"),
    ("budget_shift", 0, time(10, 0), "book"),
    ("attendee_list", 1, time(9, 15), "field"),
    ("abm_account_selection", 1, time(14, 0), "targets"),
    ("write_content", 3, time(11, 0), "winner"),
    ("sixsense_segment", 3, time(15, 30), "segment"),
)


def _spend_band_id(amount: int) -> str:
    for bucket in SPEND_FILTERS:
        ceiling = bucket["max"]
        if amount >= int(bucket["min"]) and (ceiling is None or amount <= int(ceiling)):
            return str(bucket["id"])
    return "enterprise"


def _money(amount: int) -> str:
    value = int(amount or 0)
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${round(value / 1_000)}k"
    return f"${value:,}"


def _quarter(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3 + 1


def _quarter_end(day: date) -> date:
    last_month = ((day.month - 1) // 3 + 1) * 3
    return date(day.year, last_month, monthrange(day.year, last_month)[1])


def _in_time_window(row: dict[str, Any], window: str, today: date) -> bool:
    close = date.fromisoformat(str(row["end_date"])[:10])
    if window == "this_week":
        start = today - timedelta(days=today.weekday())
        return start <= close < start + timedelta(days=7)
    if window == "this_month":
        return close.year == today.year and close.month == today.month
    if window == "this_quarter":
        return _quarter(close) == _quarter(today)
    if window == "stale":
        return (today - close).days >= 30
    return True


def _campaign_health(spend: int, mqls: int, mqls_week_ago: int) -> int:
    if mqls <= 0:
        return 32
    cost = spend / mqls
    trend = mqls - mqls_week_ago
    score = 88 - min(50, int(cost / 40)) + min(12, trend)
    return max(18, min(96, score))


def _theme(name: str) -> str:
    if " - " in name:
        return name.split(" - ", 1)[1]
    return name


def _cost_per_mql(row: dict[str, Any]) -> int:
    mqls = int(row.get("mqls") or 0)
    spend = int(row.get("spend") or 0)
    if mqls <= 0:
        return spend
    return round(spend / mqls)


def _days_to_end(row: dict[str, Any], today: date) -> int:
    close = date.fromisoformat(str(row["end_date"])[:10])
    return (close - today).days


def _end_label(row: dict[str, Any], today: date) -> str:
    close = date.fromisoformat(str(row["end_date"])[:10])
    stamp = close.strftime("%-d %b")
    days = (close - today).days
    if days >= 0:
        return f"ends {stamp} ({days} days)"
    return f"ended {stamp} ({abs(days)} days ago)"


def _detail(row: dict[str, Any], today: date) -> str:
    return (
        f"{row['id']} · {row['geo']} · {row['type']} · "
        f"{_money(int(row['spend']))} spend · {row['mqls']} MQLs · "
        f"${_cost_per_mql(row):,}/MQL · {_end_label(row, today)}"
    )


def _campaign_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for campaign in get_connectors().sfdc.list_campaigns():
        amount = int(campaign.spend_usd)
        close = BOOK_ENDS.get(campaign.id, campaign.end_date)
        rows.append(
            {
                "id": campaign.id,
                "name": campaign.name,
                "theme": _theme(campaign.name),
                "type": campaign.type.value,
                "spend": amount,
                "spend_band": _spend_band_id(amount),
                "geo": campaign.region.value,
                "end_date": close.isoformat(),
                "health": _campaign_health(
                    amount, int(campaign.mqls), int(campaign.mqls_one_week_ago)
                ),
                "mqls": int(campaign.mqls),
                "opps_created": int(campaign.opps_created),
                "leads": int(campaign.leads),
                "backup": amount >= 75_000 and int(campaign.opps_created) <= 2,
            }
        )
    return rows


def _type_filters(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen = {row["type"] for row in rows}
    ordered = [item for item in TYPE_ORDER if item in seen]
    ordered.extend(sorted(seen - set(ordered)))
    return [{"id": item, "label": TYPE_SHORT.get(item, item)} for item in ordered]


def _coverage_row(geos: list[str]) -> dict[str, Any]:
    table = coverage_by_region(get_connectors())
    key = geos[0] if len(geos) == 1 else "TOTAL"
    for row in table.rows:
        if row["Region"] == key:
            return row
    return table.rows[-1]


def _row_in_view(
    row: dict[str, Any],
    *,
    geos: list[str],
    spend: list[str],
    types: list[str],
    windows: list[str],
    today: date,
    skip: str = "",
) -> bool:
    if skip != "geo" and geos and row["geo"] not in geos:
        return False
    if skip != "spend" and spend and row["spend_band"] not in spend:
        return False
    if skip != "type" and types and row["type"] not in types:
        return False
    if skip != "window" and windows and not any(
        _in_time_window(row, window, today) for window in windows
    ):
        return False
    return True


def _mention_when(raw: str) -> str:
    try:
        return date.fromisoformat(str(raw)[:10]).strftime("%-d %b")
    except ValueError:
        return str(raw)


def _slack_person(author: str) -> tuple[str, str]:
    handle = str(author or "teammate").strip()
    if handle.startswith("@"):
        handle = handle[1:]
    if handle.lower().startswith("u/"):
        handle = handle[2:]
    words = [
        part
        for part in handle.replace(".", " ").replace("_", " ").replace("-", " ").split()
        if part
    ]
    name = " ".join(word.capitalize() for word in words) or "Teammate"
    initials = "".join(word[0] for word in words[:2]).upper() or "?"
    return name, initials


def _slack_time(raw: str, seed: str) -> str:
    minutes = 9 * 60 + (sum(ord(c) for c in seed) % (8 * 60))
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    clock = f"{hour12}:{minute:02d} {suffix}"
    day = _mention_when(raw)
    if not day:
        return clock
    return f"{day} at {clock}"


def _slack() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        mentions = load("social_mentions.json")
    except Exception:  # pragma: no cover - fixture missing
        mentions = []
    for mention in list(mentions)[:5]:
        platform = str(mention.get("platform") or "")
        raw_author = str(mention.get("author") or "")
        name, initials = _slack_person(raw_author)
        seed = str(mention.get("id") or raw_author)
        items.append(
            {
                "id": str(mention.get("id") or seed),
                "channel": SLACK_CHANNELS.get(platform, "#marketing"),
                "from": name,
                "initials": initials,
                "when": _slack_time(str(mention.get("date") or ""), seed),
                "text": str(mention.get("text") or ""),
                "work": True,
            }
        )
    return items


def _task_bar(today: date) -> list[dict[str, Any]]:
    catalog = marketing_catalog()
    by_id = {
        item["id"]: (group["label"], item)
        for group in catalog.get("tasks", [])
        for item in group["items"]
    }
    rows: list[dict[str, Any]] = []
    for item_id, offset, clock, scope in _TASK_PICKS:
        packed = by_id.get(item_id)
        if not packed:
            continue
        group_label, item = packed
        when = datetime.combine(today + timedelta(days=offset), clock)
        if offset == 0:
            due = f"Today {clock.hour}:{clock.minute:02d}"
        elif offset == 1:
            due = f"Tomorrow {clock.hour}:{clock.minute:02d}"
        else:
            due = f"{when.strftime('%a')} {clock.hour}:{clock.minute:02d}"
        rows.append(
            {
                "id": item_id,
                "group": group_label,
                "label": item["label"],
                "due": due,
                "due_at": when.isoformat(timespec="minutes"),
                "scope": scope,
            }
        )
    rows.sort(key=lambda row: row["due_at"])
    return rows


def _alerts(
    rows: list[dict[str, Any]],
    today: date,
    *,
    coverage: dict[str, Any],
    geos: list[str],
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    wrapping = [row for row in rows if _in_time_window(row, "this_week", today)]
    for row in wrapping[:2]:
        days = max(0, _days_to_end(row, today))
        notes.append(
            {
                "id": f"nt-{row['id']}-ends",
                "kind": "task",
                "title": (
                    f"{row['theme']} ends in {days} days at "
                    f"${_cost_per_mql(row):,}/MQL"
                ),
                "detail": _detail(row, today),
                "account": row["name"],
                "due": "This week",
            }
        )
    for row in [row for row in rows if row["backup"]][:2]:
        notes.append(
            {
                "id": f"nt-{row['id']}-budget",
                "kind": "task",
                "title": (
                    f"{row['name']} is {_money(int(row['spend']))} for "
                    f"{row['opps_created']} opps"
                ),
                "detail": _detail(row, today),
                "account": row["name"],
                "due": "Budget",
            }
        )
    gap = int(coverage.get("Gap to target (USD)") or 0)
    if gap > 0:
        geo = geos[0] if len(geos) == 1 else "The book"
        days_left = max(0, (_quarter_end(today) - today).days)
        notes.append(
            {
                "id": "nt-coverage-gap",
                "kind": "task",
                "title": f"{geo} is {_money(gap)} short of target",
                "detail": f"{days_left} days left · coverage {coverage.get('Coverage', '')}",
                "account": "",
                "due": "Quarter",
            }
        )
    stale = [row for row in rows if _in_time_window(row, "stale", today)]
    for row in stale[:2]:
        notes.append(
            {
                "id": f"nt-{row['id']}-stale",
                "kind": "task",
                "title": f"{row['name']} {_end_label(row, today)}",
                "detail": _detail(row, today),
                "account": row["name"],
                "due": "Stale",
            }
        )
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for note in notes:
        if note["id"] in seen:
            continue
        seen.add(note["id"])
        unique.append(note)
    return unique[:8]


def dashboard_payload(
    *,
    geos: list[str] | None = None,
    spend: list[str] | None = None,
    types: list[str] | None = None,
    windows: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Marketing campaign book, folded onto the shared dashboard contract."""
    today = today or AS_OF
    geos = [item for item in (geos or []) if item]
    spend_bands = [item for item in (spend or []) if item]
    types = [item for item in (types or []) if item]
    windows = [item for item in (windows or []) if item]

    book = _campaign_rows()
    visible = [
        row
        for row in book
        if _row_in_view(
            row, geos=geos, spend=spend_bands, types=types, windows=windows, today=today
        )
    ]
    spend_rows = [
        row
        for row in book
        if _row_in_view(
            row,
            geos=geos,
            spend=spend_bands,
            types=types,
            windows=windows,
            today=today,
            skip="spend",
        )
    ]
    type_rows = [
        row
        for row in book
        if _row_in_view(
            row,
            geos=geos,
            spend=spend_bands,
            types=types,
            windows=windows,
            today=today,
            skip="type",
        )
    ]

    type_filters = _type_filters(book)
    by_stage = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in type_filters
    }
    by_size = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in SPEND_FILTERS
    }
    for row in type_rows:
        bucket = by_stage.get(row["type"])
        if bucket:
            bucket["count"] += 1
            bucket["amount"] += row["spend"]
    for row in spend_rows:
        bucket = by_size.get(row["spend_band"])
        if bucket:
            bucket["count"] += 1
            bucket["amount"] += row["spend"]

    opps = [
        {
            "id": row["id"],
            "account": row["name"],
            "name": row["name"],
            "stage": row["type"],
            "amount": row["spend"],
            "size": row["spend_band"],
            "geo": row["geo"],
            "owner": "",
            "health": row["health"],
            "close_date": row["end_date"],
            "backup": row["backup"],
        }
        for row in visible
    ]

    coverage = _coverage_row(geos)
    slack = _slack()
    total_spend = sum(int(row["spend"]) for row in visible)
    closing_week = [row for row in visible if _in_time_window(row, "this_week", today)]

    return {
        "as_of": today.isoformat(),
        "copy": {
            "kicker": "SailPoint · Marketing",
            "title": "Campaigns",
            "kpi_pipeline": "Spend in view",
            "kpi_pipeline_hint": "Click to clear spend & type",
            "kpi_open": "Campaigns",
            "kpi_open_hint": "Jump to the book",
            "kpi_week": "Ending this week",
            "kpi_week_hint": "Click to filter this week",
            "kpi_week_filter": "this_week",
            "kpi_slack": "Slack",
            "kpi_slack_hint": "Open the feed",
            "empty": "No campaigns match these filters.",
            "unit": "campaigns",
            "table": "Campaigns",
            "stage_chart": "Spend by type",
            "size_chart": "Mix by spend band",
            "filter_size": "Spend",
            "filter_stage": "Type",
            "filter_time": "Time",
            "filter_geo": "Region",
            "col_id": "Campaign",
            "col_name": "Name",
            "col_stage": "Type",
            "col_size": "Spend band",
            "col_amount": "Spend",
            "col_close": "Ends",
            "col_health": "Health",
        },
        "filters": {
            "sizes": [
                {"id": item["id"], "label": item["label"]} for item in SPEND_FILTERS
            ],
            "stages": type_filters,
            "windows": [dict(item) for item in TIME_FILTERS],
            "geos": [
                {"id": "AMER", "label": "AMER"},
                {"id": "EMEA", "label": "EMEA"},
                {"id": "APJ", "label": "APJ"},
            ],
        },
        "kpis": {
            "pipeline": total_spend,
            "open_opps": len(visible),
            "closing_week": len(closing_week),
            "slack_work": len(slack),
        },
        "by_stage": list(by_stage.values()),
        "by_size": list(by_size.values()),
        "opps": opps,
        "tasks": _task_bar(today),
        "notifications": _alerts(visible, today, coverage=coverage, geos=geos),
        "slack": slack,
        "connectors": [
            {"id": "salesforce", "label": "Salesforce campaigns", "status": "mock"},
            {"id": "chat", "label": "Chat artifacts", "status": "local"},
        ],
    }


def create_app(
    *,
    runner: Any | None = None,
    session_service: InMemorySessionService | None = None,
) -> FastAPI:
    sessions = session_service or InMemorySessionService()
    live_runner = runner
    app = FastAPI(title="James", docs_url=None, redoc_url=None)

    def get_runner() -> Any:
        nonlocal live_runner
        if live_runner is None:
            from dotenv import load_dotenv

            # `adk web` reads .env for you; running uvicorn directly does not.
            load_dotenv(MARKETING_ROOT / ".env")
            from root.app import build_runner

            live_runner = build_runner(APP_NAME, session_service=sessions)
        return live_runner

    async def ensure_session(session_id: str) -> str:
        sid = session_id.strip() or str(uuid.uuid4())
        existing = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=sid
        )
        if existing is None:
            existing = await sessions.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=sid
            )
        return existing.id

    @app.get("/api/workspace")
    async def workspace() -> dict[str, Any]:
        return workspace_catalog()

    @app.get("/api/dashboard")
    async def dashboard(
        geos: str = "",
        sizes: str = "",
        stages: str = "",
        windows: str = "",
    ) -> dict[str, Any]:
        def split(raw: str) -> list[str]:
            return [part.strip() for part in raw.split(",") if part.strip()]

        # The shell speaks in size/stage buckets; marketing reads them as
        # spend bands and campaign types.
        return dashboard_payload(
            geos=split(geos),
            spend=split(sizes),
            types=split(stages),
            windows=split(windows),
        )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        session = await sessions.create_session(app_name=APP_NAME, user_id=USER_ID)
        return {"session_id": session.id}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        session = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session.id}

    async def chat_stream(
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list[Any],
    ) -> AsyncIterator[str]:
        yield _sse({"type": "prompt", "text": visible})
        seen_status = {THINKING_LABEL}
        yield _sse({"type": "status", "label": THINKING_LABEL})
        parts = [types.Part.from_text(text=message)]
        parts.extend(
            types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
            for item in inline
        )
        final_text = ""
        reasoning = ""
        try:
            async for event in get_runner().run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts),
                run_config=RUN_CONFIG,
            ):
                label = status_for_author(event.author or "")
                if label and label not in seen_status:
                    seen_status.add(label)
                    yield _sse({"type": "status", "label": label})
                thought = _event_text(event, thoughts=True).strip()
                if thought and thought != reasoning:
                    reasoning = thought
                    yield _sse(
                        {"type": "reasoning", "kind": "thought", "text": reasoning}
                    )
                text = _event_text(event).strip()
                if text and event.is_final_response():
                    final_text = text
        except Exception as exc:
            log.exception("James chat failed")
            yield _sse(
                {
                    "type": "error",
                    "message": "James couldn't complete that request. Try again.",
                    "detail": type(exc).__name__,
                }
            )
            yield _sse({"type": "done"})
            return

        if not final_text:
            yield _sse(
                {"type": "error", "message": "James didn't return an answer. Try again."}
            )
        else:
            payload = parse_reply(final_text)
            if payload["kind"] == "plain":
                for chunk in word_deltas(payload["text"]):
                    yield _sse({"type": "delta", "text": chunk})
            yield _sse({"type": "reply", **payload})
        yield _sse({"type": "reasoning_done"})
        yield _sse({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        selection = _selection(body.filters)
        decoded = decode_attachments(
            [attachment.model_dump() for attachment in body.attachments]
        )
        message = _compose_message(body, selection)
        if not message and decoded:
            message = "Review the attached files."
        if not message:
            raise HTTPException(status_code=400, detail="Message is empty")
        filenames = [item.filename for item in decoded]
        visible = message
        if filenames:
            visible += "\n\nAttached: " + ", ".join(filenames)
        prompt, inline = prompt_and_inline(message, decoded)
        session_id = await ensure_session(body.session_id)
        return StreamingResponse(
            chat_stream(session_id, prompt, visible=visible, inline=inline),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    return app


app = create_app()
