"""Henry adapter for the shared GRU browser shell."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
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
