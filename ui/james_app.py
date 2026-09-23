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
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

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
