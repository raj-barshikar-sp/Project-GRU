"""Henry adapter for the shared GRU browser shell."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ui.attachments import decode_attachments, prompt_and_inline
from ui.briefing import parse_reply
from ui.stream import word_deltas


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


SIZE_BUCKETS = (
    {"id": "under_500k", "label": "Under $500k", "min": 0, "max": 499_999},
    {"id": "500k_1m", "label": "$500k–$1M", "min": 500_000, "max": 999_999},
    {"id": "over_1m", "label": "$1M+", "min": 1_000_000, "max": None},
)


def _size_id(amount: float) -> str:
    for bucket in SIZE_BUCKETS:
        ceiling = bucket["max"]
        if amount >= float(bucket["min"]) and (
            ceiling is None or amount <= float(ceiling)
        ):
            return str(bucket["id"])
    return "over_1m"


def workspace_catalog(orchestrator: Any) -> dict[str, Any]:
    accounts = list(orchestrator.sfdc_tool._repository.all())
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in orchestrator.dsr_ask_catalog.catalog():
        category = entry.category.value
        groups.setdefault(category, []).append(
            {
                "id": entry.action.value,
                "label": entry.title,
                "default_prompt": f"{entry.title}: {entry.description}",
                "scoped_prompt": f"{entry.title}: {entry.description}",
                "filters": [],
            }
        )

    used_sizes = {
        _size_id(float(account.open_opportunity_amount or 0)) for account in accounts
    }
    return {
        "assistant": {
            "name": "Henry",
            "title": "Henry the DSR Minion",
            "tagline": "Prospect, plan, engage, and progress digital sales rooms.",
        },
        "tasks": [
            {
                "id": category,
                "label": category.replace("_", " ").title(),
                "agent": "henry",
                "items": items,
            }
            for category, items in groups.items()
        ],
        "filters": {
            "geos": [
                {"id": value, "label": f"Territory: {value}"}
                for value in sorted({account.territory for account in accounts})
            ],
            "boats": [
                {"id": value, "label": f"Owner: {value}"}
                for value in sorted({account.owner_id for account in accounts})
            ],
            "opps": [
                {
                    "id": account.id,
                    "account": account.name,
                    "territory": account.territory,
                    "owner": account.owner_id,
                    "label": f"{account.name} · {account.stage} · {account.id}",
                }
                for account in accounts
            ],
            "report_types": [
                {"id": value, "label": value}
                for value in sorted({account.industry for account in accounts})
            ],
            "sizes": [
                {"id": str(bucket["id"]), "label": str(bucket["label"])}
                for bucket in SIZE_BUCKETS
                if bucket["id"] in used_sizes
            ],
            "stages": [
                {"id": value, "label": value}
                for value in sorted({account.stage for account in accounts})
            ],
            "windows": [],
        },
        "ui": {"reasoning": False},
    }


def _filter_notes(filters: ChatFilters | None) -> list[str]:
    if filters is None:
        return []
    values = filters.model_dump()
    labels = {
        "geos": "Territories",
        "boats": "Owners",
        "report_types": "Industries",
        "sizes": "Opportunity size",
        "stages": "Sales stage",
    }
    return [
        f"{labels[key]}: {', '.join(values[key])}"
        for key in labels
        if values[key]
    ]


def _in_time_window(day: date, window: str, today: date) -> bool:
    if window == "this_week":
        start = today - timedelta(days=today.weekday())
        return start <= day < start + timedelta(days=7)
    if window == "this_month":
        return day.year == today.year and day.month == today.month
    if window == "stale":
        return (today - day).days >= 30
    return True


TIME_FILTERS = (
    {"id": "this_week", "label": "Touched this week"},
    {"id": "this_month", "label": "Touched this month"},
    {"id": "stale", "label": "Stale 30d+"},
)


def dashboard_payload(
    orchestrator: Any,
    *,
    geos: list[str] | None = None,
    boats: list[str] | None = None,
    sizes: list[str] | None = None,
    stages: list[str] | None = None,
    windows: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Account book for the shared dashboard chrome."""
    today = today or date.today()
    geos = [item for item in (geos or []) if item]
    boats = [item for item in (boats or []) if item]
    sizes = [item for item in (sizes or []) if item]
    stages = [item for item in (stages or []) if item]
    windows = [item for item in (windows or []) if item]
    accounts = list(orchestrator.sfdc_tool._repository.all())
    rows: list[dict[str, Any]] = []
    for account in accounts:
        amount = int(account.open_opportunity_amount or 0)
        touched = date.fromisoformat(str(account.last_activity_date)[:10])
        health = max(18, min(96, 88 - min(50, int(account.days_in_stage)) + (8 if account.bva_complete else 0)))
        rows.append(
            {
                "id": account.id,
                "account": account.name,
                "stage": str(account.stage or "SS20"),
                "amount": amount,
                "size": _size_id(amount),
                "geo": account.territory,
                "owner": account.owner_id,
                "health": health,
                "close_date": touched.isoformat(),
                "backup": amount <= 0,
                "industry": account.industry,
                "stale": (today - touched).days >= 30,
            }
        )
    visible = []
    for row in rows:
        if geos and row["geo"] not in geos:
            continue
        if boats and row["owner"] not in boats:
            continue
        if sizes and row["size"] not in sizes:
            continue
        if stages and row["stage"] not in stages:
            continue
        if windows and not any(
            _in_time_window(date.fromisoformat(row["close_date"]), window, today)
            for window in windows
        ):
            continue
        visible.append(row)

    catalog = workspace_catalog(orchestrator)["filters"]
    by_stage = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in catalog.get("stages") or []
    }
    by_size = {
        item["id"]: {"id": item["id"], "label": item["label"], "count": 0, "amount": 0}
        for item in SIZE_BUCKETS
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

    notifications = [
        {
            "id": f"nt-{row['id']}",
            "kind": "task",
            "title": f"{row['account']} needs a touch",
            "detail": f"{row['stage']} · last activity {row['close_date']}",
            "account": row["account"],
            "due": "This week" if row["stale"] else "Soon",
        }
        for row in visible
        if row["stale"] or row["health"] < 55
    ][:8]
    slack = [
        {
            "id": "sl-1",
            "channel": "#dsr-west",
            "from": "Avery Cole",
            "when": "Today 9:05",
            "text": "Apex Financial still has no BVA. Can Henry draft the room agenda?",
            "work": True,
            "account": "Apex Financial",
        },
        {
            "id": "sl-2",
            "channel": "#digital-rooms",
            "from": "Jordan Hale",
            "when": "Today 8:12",
            "text": "Meridian wants the 360 pack before Thursday's working session.",
            "work": True,
            "account": "Meridian Health Network",
        },
        {
            "id": "sl-3",
            "channel": "#se-sync",
            "from": "Sam Rivera",
            "when": "Yesterday",
            "text": "Whitespace on US-WEST lookalikes is ready if we want a prospecting pass.",
            "work": True,
            "account": "",
        },
    ]
    catalog_tasks = [
        item
        for group in workspace_catalog(orchestrator)["tasks"]
        for item in group["items"]
    ]
    picks = catalog_tasks[:5]
    clocks = (time(8, 20), time(9, 45), time(11, 10), time(14, 0), time(16, 15))
    tasks = []
    for index, item in enumerate(picks):
        clock = clocks[index]
        offset = 0 if index < 3 else 1
        when = datetime.combine(today + timedelta(days=offset), clock)
        due = (
            f"Today {clock.hour}:{clock.minute:02d}"
            if offset == 0
            else f"Tomorrow {clock.hour}:{clock.minute:02d}"
        )
        tasks.append(
            {
                "id": item["id"],
                "label": item["label"],
                "due": due,
                "due_at": when.isoformat(timespec="minutes"),
                "scope": visible[index]["account"] if index < len(visible) else "book",
            }
        )
    pipeline = sum(row["amount"] for row in visible if not row["backup"])
    return {
        "as_of": today.isoformat(),
        "copy": {
            "kicker": "SailPoint · DSR",
            "title": "Account book",
            "kpi_pipeline": "Open pipeline",
            "kpi_pipeline_hint": "Click to clear size & stage",
            "kpi_open": "Accounts",
            "kpi_open_hint": "Jump to the book",
            "kpi_week": "Stale 30d+",
            "kpi_week_hint": "Click to filter stale accounts",
            "kpi_week_filter": "stale",
            "kpi_slack": "Room Slack",
            "kpi_slack_hint": "Open the feed",
            "empty": "No accounts match these filters.",
            "unit": "accounts",
            "table": "Accounts",
            "stage_chart": "Pipeline by stage",
            "size_chart": "Mix by opp size",
            "filter_size": "Opp size",
            "filter_stage": "Stage",
            "filter_time": "Activity",
            "filter_geo": "Territory",
            "col_id": "Acc",
            "col_name": "Account",
            "col_stage": "Stage",
            "col_size": "Size",
            "col_amount": "Amount",
            "col_close": "Last touch",
            "col_health": "Health",
        },
        "filters": {
            "sizes": catalog.get("sizes") or [dict(item) for item in SIZE_BUCKETS],
            "stages": catalog.get("stages") or [],
            "windows": [dict(item) for item in TIME_FILTERS],
            "geos": catalog.get("geos") or [],
        },
        "kpis": {
            "pipeline": pipeline,
            "open_opps": len(visible),
            "closing_week": len([row for row in visible if row["stale"]]),
            "slack_work": len(slack),
        },
        "by_stage": list(by_stage.values()),
        "by_size": list(by_size.values()),
        "opps": visible,
        "tasks": tasks,
        "notifications": notifications,
        "slack": slack,
        "connectors": [
            {"id": "salesforce", "label": "Salesforce", "status": "connected"},
            {"id": "slack", "label": "Slack", "status": "local"},
        ],
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_app(*, orchestrator: Any | None = None) -> FastAPI:
    if orchestrator is None:
        from henry_dsr_agent.orchestrator import HenryOrchestrator

        orchestrator = HenryOrchestrator()

    app = FastAPI(title="Henry", docs_url=None, redoc_url=None)
    sessions: set[str] = set()

    def ensure_session(session_id: str = "") -> str:
        value = session_id.strip() or str(uuid.uuid4())
        sessions.add(value)
        return value

    @app.get("/api/workspace")
    async def workspace() -> dict[str, Any]:
        return workspace_catalog(orchestrator)

    @app.get("/api/dashboard")
    async def dashboard(
        geos: str = "",
        boats: str = "",
        sizes: str = "",
        stages: str = "",
        windows: str = "",
    ) -> dict[str, Any]:
        def split(raw: str) -> list[str]:
            return [part.strip() for part in raw.split(",") if part.strip()]

        return dashboard_payload(
            orchestrator,
            geos=split(geos),
            boats=split(boats),
            sizes=split(sizes),
            stages=split(stages),
            windows=split(windows),
        )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        return {"session_id": ensure_session()}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session_id}

    async def stream(
        session_id: str,
        message: str,
        visible: str,
        task_id: str,
        filters: ChatFilters | None,
    ) -> AsyncIterator[str]:
        yield _sse({"type": "prompt", "text": visible})
        yield _sse({"type": "status", "label": "Henry is working…"})
        notes = _filter_notes(filters)
        if notes and "Working filters:" not in message:
            message += "\n\nWorking filters:\n" + "\n".join(f"- {note}" for note in notes)
        account_id = filters.opps[0] if filters and filters.opps else None
        actions = {
            entry.action.value for entry in orchestrator.dsr_ask_catalog.catalog()
        }
        if task_id and task_id not in actions:
            yield _sse({"type": "error", "message": "Unknown Henry task."})
            yield _sse({"type": "done"})
            return
        try:
            result = await orchestrator.chat(
                {
                    "message": message,
                    "account_id": account_id,
                    "action": task_id or None,
                    "action_locked": bool(task_id),
                    "context": {},
                }
            )
            text = str(result.markdown)
        except Exception as exc:
            yield _sse(
                {
                    "type": "error",
                    "message": "Henry couldn't complete that request. Try again.",
                    "detail": type(exc).__name__,
                }
            )
            yield _sse({"type": "done"})
            return
        for chunk in word_deltas(text):
            yield _sse({"type": "delta", "text": chunk})
        yield _sse({"type": "reply", **parse_reply(text)})
        yield _sse({"type": "reasoning_done"})
        yield _sse({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        message = body.message.strip()
        decoded = decode_attachments(
            [attachment.model_dump() for attachment in body.attachments]
        )
        if not message and decoded:
            message = "Review the attached files."
        if not message:
            raise HTTPException(status_code=400, detail="Message is empty")
        visible = message
        if decoded:
            visible += "\n\nAttached: " + ", ".join(item.filename for item in decoded)
        message, _inline = prompt_and_inline(message, decoded)
        session_id = ensure_session(body.session_id)
        return StreamingResponse(
            stream(session_id, message, visible, body.task_id, body.filters),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    return app


app = create_app()
