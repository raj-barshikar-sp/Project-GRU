"""Stuart HTTP adapter for the shared GRU browser shell."""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from ui.attachments import decode_attachments, prompt_and_inline
from ui.briefing import parse_reply
from ui.stream import word_deltas

APP_NAME = "stuart-sales-manager"
USER_ID = "manager"
SESSION_KEYS = ("ae_name", "last_account", "last_territory", "last_opportunity")
FILTER_KEYS = (
    "geos",
    "boats",
    "opps",
    "report_types",
    "sizes",
    "stages",
    "windows",
)
FILTER_NOTE_LABELS = {
    "geos": "Books",
    "boats": "Reps",
    "opps": "Opportunities",
    "report_types": "Forecast categories",
    "sizes": "Deal size",
    "stages": "Sales stage",
    "windows": "Fiscal quarter",
}
log = logging.getLogger("stuart.ui")

STATUS_BY_AUTHOR = {
    "route_planner": "Understanding the manager request…",
    "crm_intelligence_specialist": "Checking CRM intelligence…",
    "activity_engagement_specialist": "Reviewing account activity…",
    "rep_performance_specialist": "Reviewing rep performance…",
    "forecast_modeling_specialist": "Modeling the forecast…",
    "knowledge_base_rag": "Checking manager guidance…",
    "synthesis": "Putting that together…",
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


SIZE_BUCKETS = (
    {"id": "under_250k", "label": "Under $250k", "min": 0, "max": 249_999},
    {"id": "250k_500k", "label": "$250k–$500k", "min": 250_000, "max": 499_999},
    {"id": "over_500k", "label": "$500k+", "min": 500_000, "max": None},
)


def _task(task_id: str, label: str, prompt: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "label": label,
        "default_prompt": prompt,
        "scoped_prompt": prompt,
        "filters": [],
    }


def _size_id(amount: float) -> str:
    for bucket in SIZE_BUCKETS:
        ceiling = bucket["max"]
        if amount >= float(bucket["min"]) and (
            ceiling is None or amount <= float(ceiling)
        ):
            return str(bucket["id"])
    return "over_500k"


def _stage_code(stage: str) -> str:
    return stage.split(" ", 1)[0].strip()


def _stage_label(stage: str) -> str:
    code, _, rest = stage.partition(" - ")
    return f"{code.strip()} · {rest.strip()}" if rest else code.strip()


def _catalog_filters() -> dict[str, list[dict[str, str]]]:
    """Build the right-rail catalog from Stuart's own Salesforce snapshot."""
    try:
        from agents.new_data_store import data_ready, normalized_opportunities
    except ImportError:
        return {key: [] for key in FILTER_KEYS}
    if not data_ready():
        return {key: [] for key in FILTER_KEYS}

    opportunities = normalized_opportunities()
    books = sorted({str(row.get("Boat__c") or "") for row in opportunities} - {""})
    reps = sorted({str(row.get("Owner_Name") or "") for row in opportunities} - {""})
    categories = sorted(
        {str(row.get("ForecastCategoryName") or "") for row in opportunities} - {""}
    )
    stages = sorted(
        {str(row.get("StageName") or "") for row in opportunities} - {""},
        key=_stage_code,
    )
    quarters = sorted(
        {str(row.get("Fiscal_Quarter__c") or "") for row in opportunities} - {""},
        key=lambda quarter: min(
            str(row.get("CloseDate") or "9999-12-31")
            for row in opportunities
            if row.get("Fiscal_Quarter__c") == quarter
        ),
    )
    used_sizes = {_size_id(float(row.get("Amount") or 0)) for row in opportunities}
    return {
        "geos": [{"id": book, "label": f"Book: {book}"} for book in books],
        "boats": [{"id": rep, "label": f"Rep: {rep}"} for rep in reps],
        "opps": [
            {
                "id": str(row["Id"]),
                "account": row["Account_Name"],
                "territory": str(row.get("Boat__c") or ""),
                "owner": str(row.get("Owner_Name") or ""),
                "label": (
                    f"{row['Account_Name']} · "
                    f"{_stage_code(str(row.get('StageName') or ''))} · "
                    f"{row['Id']}"
                ),
            }
            for row in opportunities
        ],
        "report_types": [
            {"id": category, "label": f"Forecast: {category}"}
            for category in categories
        ],
        "sizes": [
            {"id": str(bucket["id"]), "label": str(bucket["label"])}
            for bucket in SIZE_BUCKETS
            if bucket["id"] in used_sizes
        ],
        "stages": [
            {"id": _stage_code(stage), "label": _stage_label(stage)}
            for stage in stages
        ],
        "windows": [{"id": quarter, "label": quarter} for quarter in quarters],
    }


def workspace_catalog() -> dict[str, Any]:
    return {
        "assistant": {
            "name": "Stuart",
            "title": "Stuart the Sales Manager Assistant",
            "tagline": "Forecast, coach, and inspect the team from one workspace.",
        },
        "tasks": [
            {
                "id": "forecasting",
                "label": "Forecasting",
                "agent": "forecast_modeling_specialist",
                "items": [
                    _task(
                        "regional_forecast",
                        "Regional forecast",
                        "Review the regional forecast and flag the largest risks and upside.",
                    ),
                    _task(
                        "forecast_changes",
                        "Forecast changes",
                        "What changed in the forecast since the last review?",
                    ),
                ],
            },
            {
                "id": "forecast_inspection",
                "label": "Forecast inspection",
                "agent": "crm_intelligence_specialist",
                "items": [
                    _task(
                        "stage_validation",
                        "Sales stage validation",
                        "Inspect active opportunities for stage, next-step, and close-date risk.",
                    ),
                    _task(
                        "pipeline_risk",
                        "Pipeline risk",
                        "Find the deals most likely to slip and explain why.",
                    ),
                ],
            },
            {
                "id": "rep_participation",
                "label": "Rep participation",
                "agent": "rep_performance_specialist",
                "items": [
                    _task(
                        "rep_performance",
                        "Rep performance",
                        "Summarize rep performance and identify where coaching is needed.",
                    ),
                    _task(
                        "account_activity",
                        "Account activity",
                        "Show accounts with weak engagement or missing follow-up.",
                    ),
                ],
            },
            {
                "id": "future_pipeline",
                "label": "Future quarter pipeline",
                "agent": "forecast_modeling_specialist",
                "items": [
                    _task(
                        "future_coverage",
                        "Future coverage",
                        "Assess future-quarter pipeline coverage and creation gaps.",
                    )
                ],
            },
            {
                "id": "manager_guidance",
                "label": "Manager policy & knowledge",
                "agent": "knowledge_base_rag",
                "items": [
                    _task(
                        "knowledge_base",
                        "Manager guidance",
                        "Answer my sales-management question using the available guidance.",
                    )
                ],
            },
        ],
        "filters": _catalog_filters(),
        "ui": {
            "reasoning": os.getenv("SELLER_COPILOT_UI_REASONING", "1").lower()
            not in {"0", "false", "no"}
        },
    }


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


def _context(state: Any) -> dict[str, str]:
    return {key: str(state.get(key) or "") for key in SESSION_KEYS}


def _label_index() -> dict[str, dict[str, str]]:
    """Map filter ids to note text; ids that are already names need no label."""
    catalog = workspace_catalog()["filters"]
    return {
        key: {item["id"]: item["label"] for item in catalog.get(key, [])}
        for key in ("opps", "sizes", "stages")
    }


def filter_notes(filters: ChatFilters | None) -> list[str]:
    """Turn ticked right-rail values into lines the specialists can read."""
    if filters is None:
        return []
    selected = filters.model_dump()
    if not any(selected.values()):
        return []
    labels = _label_index()
    notes: list[str] = []
    for key in FILTER_KEYS:
        values = selected.get(key) or []
        if not values:
            continue
        readable = [labels.get(key, {}).get(value, value) for value in values]
        notes.append(f"{FILTER_NOTE_LABELS[key]}: {', '.join(readable)}")
    return notes


def apply_filter_notes(text: str, filters: ChatFilters | None) -> str:
    notes = filter_notes(filters)
    if not notes:
        return text
    return text + "\n\nWorking filters:\n" + "\n".join(f"- {note}" for note in notes)


def task_prompt(task_id: str) -> str:
    for group in workspace_catalog()["tasks"]:
        for item in group["items"]:
            if item["id"] == task_id:
                return str(item["default_prompt"])
    raise KeyError(task_id)


def _close_day(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def _in_week(day: date, today: date) -> bool:
    start = today - timedelta(days=today.weekday())
    return start <= day < start + timedelta(days=7)


def dashboard_payload(
    *,
    geos: list[str] | None = None,
    boats: list[str] | None = None,
    sizes: list[str] | None = None,
    stages: list[str] | None = None,
    windows: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Team forecast book for the shared dashboard chrome."""
    today = today or date.today()
    geos = [item for item in (geos or []) if item]
    boats = [item for item in (boats or []) if item]
    sizes = [item for item in (sizes or []) if item]
    stages = [item for item in (stages or []) if item]
    windows = [item for item in (windows or []) if item]
    try:
        from agents.new_data_store import data_ready, normalized_opportunities
    except ImportError:
        opportunities: list[dict[str, Any]] = []
    else:
        opportunities = normalized_opportunities() if data_ready() else []

    rows: list[dict[str, Any]] = []
    for item in opportunities:
        amount = int(item.get("Amount") or 0)
        stage = _stage_code(str(item.get("StageName") or ""))
        close = str(item.get("CloseDate") or today.isoformat())
        rows.append(
            {
                "id": str(item.get("Id") or ""),
                "account": str(item.get("Account_Name") or item.get("Name") or ""),
                "stage": stage,
                "amount": amount,
                "size": _size_id(amount),
                "geo": str(item.get("Boat__c") or ""),
                "owner": str(item.get("Owner_Name") or ""),
                "health": int(item.get("CRM_Score__c") or 0),
                "close_date": close,
                "backup": bool(item.get("Backup_Deal_Id__c")),
                "quarter": str(item.get("Fiscal_Quarter__c") or ""),
                "category": str(item.get("ForecastCategoryName") or ""),
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
        if windows and row["quarter"] not in windows:
            continue
        visible.append(row)

    catalog = _catalog_filters()
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

    closing_week = [
        row
        for row in visible
        if _in_week(_close_day(row["close_date"]), today)
    ]
    notifications = [
        {
            "id": f"nt-{row['id']}",
            "kind": "task",
            "title": f"{row['account']} needs a manager look",
            "detail": f"{row['stage']} · health {row['health']}",
            "account": row["account"],
            "due": "This week" if row in closing_week else "Soon",
        }
        for row in visible
        if row["health"] and row["health"] < 70
    ][:8]
    slack = [
        {
            "id": "sl-1",
            "channel": "#forecast-review",
            "from": "Marcus Vance",
            "when": "Today 8:40",
            "text": "Walk the commit stack before Friday. Flag any SS70 without a next step.",
            "work": True,
            "account": "",
        },
        {
            "id": "sl-2",
            "channel": "#west-managers",
            "from": "Elena Rodriguez",
            "when": "Today 7:55",
            "text": "Financial Services coverage is thin for next quarter. Need two new logos.",
            "work": True,
            "account": "",
        },
        {
            "id": "sl-3",
            "channel": "#coaching",
            "from": "Sarah Jenkins",
            "when": "Yesterday",
            "text": "Can we inspect Brody's ramping book this afternoon?",
            "work": True,
            "account": "",
        },
    ]
    picks = (
        ("regional_forecast", 0, time(8, 30), "team"),
        ("stage_validation", 0, time(10, 0), "commit"),
        ("rep_performance", 1, time(9, 15), "brody"),
        ("pipeline_risk", 1, time(14, 0), "west"),
        ("future_coverage", 3, time(11, 0), "q4"),
    )
    by_id = {
        item["id"]: (group["label"], item)
        for group in workspace_catalog()["tasks"]
        for item in group["items"]
    }
    tasks = []
    for item_id, offset, clock, scope in picks:
        packed = by_id.get(item_id)
        if not packed:
            continue
        group_label, item = packed
        when = datetime.combine(today + timedelta(days=offset), clock)
        due = (
            f"Today {clock.hour}:{clock.minute:02d}"
            if offset == 0
            else f"Tomorrow {clock.hour}:{clock.minute:02d}"
            if offset == 1
            else f"{when.strftime('%a')} {clock.hour}:{clock.minute:02d}"
        )
        tasks.append(
            {
                "id": item_id,
                "group": group_label,
                "label": item["label"],
                "due": due,
                "due_at": when.isoformat(timespec="minutes"),
                "scope": scope,
            }
        )
    pipeline = sum(row["amount"] for row in visible if not row["backup"])
    return {
        "as_of": today.isoformat(),
        "copy": {
            "kicker": "SailPoint · Sales manager",
            "title": "Team forecast",
            "kpi_pipeline": "Pipeline",
            "kpi_pipeline_hint": "Click to clear size & stage",
            "kpi_open": "Open opps",
            "kpi_open_hint": "Jump to the book",
            "kpi_week": "Close this week",
            "kpi_week_hint": "Deals in this week's window",
            "kpi_slack": "Manager Slack",
            "kpi_slack_hint": "Open the feed",
            "empty": "No opportunities match these filters.",
            "unit": "opps",
            "table": "Team opportunities",
            "stage_chart": "Pipeline by stage",
            "size_chart": "Mix by deal size",
            "filter_size": "Deal size",
            "filter_stage": "Stage",
            "filter_time": "Quarter",
            "filter_geo": "Book",
            "col_id": "Opp",
            "col_name": "Account",
            "col_stage": "Stage",
            "col_size": "Size",
            "col_amount": "Amount",
            "col_close": "Close",
            "col_health": "Health",
        },
        "filters": {
            "sizes": [dict(item) for item in SIZE_BUCKETS],
            "stages": catalog.get("stages") or [],
            "windows": catalog.get("windows") or [],
            "geos": catalog.get("geos") or [],
        },
        "kpis": {
            "pipeline": pipeline,
            "open_opps": len([row for row in visible if not row["backup"]]),
            "closing_week": len(closing_week),
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


def create_app(
    *,
    runner: Any | None = None,
    session_service: InMemorySessionService | None = None,
) -> FastAPI:
    sessions = session_service or InMemorySessionService()
    live_runner = runner
    app = FastAPI(title="Stuart", docs_url=None, redoc_url=None)

    def get_runner() -> Any:
        nonlocal live_runner
        if live_runner is None:
            import agents.runtime_env  # noqa: F401
            from agents.orchestrator.agent import root_agent
            from google.adk.runners import Runner

            live_runner = Runner(
                agent=root_agent,
                app_name=APP_NAME,
                session_service=sessions,
            )
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
        boats: str = "",
        sizes: str = "",
        stages: str = "",
        windows: str = "",
    ) -> dict[str, Any]:
        def split(raw: str) -> list[str]:
            return [part.strip() for part in raw.split(",") if part.strip()]

        return dashboard_payload(
            geos=split(geos),
            boats=split(boats),
            sizes=split(sizes),
            stages=split(stages),
            windows=split(windows),
        )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        session = await sessions.create_session(app_name=APP_NAME, user_id=USER_ID)
        return {"session_id": session.id, **_context(session.state)}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        session = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session.id, **_context(session.state)}

    async def chat_stream(
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list[Any],
    ) -> AsyncIterator[str]:
        yield _sse({"type": "prompt", "text": visible})
        yield _sse({"type": "status", "label": "Stuart is working…"})
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
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                label = STATUS_BY_AUTHOR.get(event.author or "")
                if label:
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
            log.exception("Stuart chat failed")
            yield _sse(
                {
                    "type": "error",
                    "message": "Stuart couldn't complete that request. Try again.",
                    "detail": type(exc).__name__,
                }
            )
            yield _sse({"type": "done"})
            return

        if not final_text:
            yield _sse(
                {"type": "error", "message": "Stuart didn't return an answer. Try again."}
            )
        else:
            payload = parse_reply(final_text)
            for chunk in word_deltas(payload["text"]):
                yield _sse({"type": "delta", "text": chunk})
            yield _sse({"type": "reply", **payload})
        session = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if session is not None:
            yield _sse({"type": "context", **_context(session.state)})
        yield _sse({"type": "reasoning_done"})
        yield _sse({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        message = body.message.strip()
        decoded = decode_attachments(
            [attachment.model_dump() for attachment in body.attachments]
        )
        if not message and body.task_id:
            try:
                message = task_prompt(body.task_id)
            except KeyError as exc:
                raise HTTPException(status_code=400, detail="Unknown task") from exc
        if not message and decoded:
            message = "Review the attached files."
        if not message:
            raise HTTPException(status_code=400, detail="Message is empty")
        if "Working filters:" not in message:
            message = apply_filter_notes(message, body.filters)
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
