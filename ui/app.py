"""FastAPI app: workspace catalog, sessions, and SSE chat to the orchestrator."""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from models.routing_decision import DomainDecision
from ui.attachments import decode_attachments, prompt_and_inline
from ui.debug_log import write as write_debug_log
from ui.briefing import parse_reply
from ui.catalog import (
    FilterSelection,
    apply_filter_notes,
    compose_task_message,
    restrict_filters,
    workspace_catalog,
)
from ui.progress import status_for_author
from ui.stream import word_deltas

APP_NAME = "seller-copilot"
STATIC_DIR = Path(__file__).with_name("static")
log = logging.getLogger("bob.chat")
SESSION_KEYS = (
    "ae_name",
    "last_account",
    "last_territory",
    "last_opportunity",
    "last_agent",
    "last_topic",
    "last_scope",
)


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


def _event_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text
        for part in event.content.parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


def _event_thought(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text
        for part in event.content.parts
        if getattr(part, "text", None) and getattr(part, "thought", False)
    )


def _event_part_summaries(event: Event) -> list[dict[str, Any]]:
    if not event.content or not event.content.parts:
        return []
    rows: list[dict[str, Any]] = []
    for part in event.content.parts:
        rows.append(
            {
                "thought": bool(getattr(part, "thought", False)),
                "text_len": len(part.text or ""),
                "has_signature": bool(getattr(part, "thought_signature", None)),
                "function": getattr(
                    getattr(part, "function_call", None), "name", None
                ),
            }
        )
    return rows


def _ui_reasoning_enabled() -> bool:
    flag = os.getenv("SELLER_COPILOT_UI_REASONING", "1").strip().lower()
    return flag not in ("0", "false", "no")


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _state_delta(event: Event) -> dict[str, Any]:
    return getattr(getattr(event, "actions", None), "state_delta", None) or {}


def _reply_from_decision(raw: Any) -> str:
    planned = DomainDecision.from_state(raw)
    return (planned.direct_reply or planned.clarifying_question).strip()


def _reply_from_event(event: Event) -> str:
    """AE-visible text from an orchestrator or planner event."""
    if event.get_function_calls() or event.get_function_responses():
        return ""
    author = event.author or ""
    harvested = _reply_from_decision(_state_delta(event).get("domain_decision"))
    if harvested:
        return harvested
    if event.output is not None:
        harvested = _reply_from_decision(event.output)
        if harvested:
            return harvested
    text = _event_text(event)
    if not text.strip():
        return ""
    if author == "route_planner":
        return _reply_from_decision(text)
    if _looks_like_json(text):
        return _reply_from_decision(text)
    if author == "orchestrator":
        return text
    return ""


def _streamable_text(event: Event) -> str:
    """Plain markdown/text the AE can watch; skip JSON, tools, and synthesis dumps."""
    return _reply_from_event(event)


def _event_chunk(event: Event) -> dict[str, Any]:
    """One Gemini/ADK stream piece. The text field is a raw chunk, not the final reply."""
    thought = _event_thought(event)
    return {
        "author": event.author,
        "partial": bool(getattr(event, "partial", False)),
        "text": _event_text(event),
        "thought": thought,
        "thought_len": len(thought),
        "parts": _event_part_summaries(event),
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _context_from_state(state: Any) -> dict[str, str]:
    return {key: str(state.get(key) or "") for key in SESSION_KEYS}


def create_app(
    *,
    runner: Any | None = None,
    session_service: InMemorySessionService | None = None,
) -> FastAPI:
    """Build the UI app. Callers may inject a fake runner and session service."""

    sessions = session_service or InMemorySessionService()
    live_runner = runner
    app = FastAPI(title="Bob", docs_url=None, redoc_url=None)

    def _runner() -> Any:
        nonlocal live_runner
        if live_runner is None:
            import agents.runtime_env  # noqa: F401 — env must load before runner builds

            from google.adk.runners import Runner

            from agents.orchestrator.agent import root_agent

            live_runner = Runner(
                agent=root_agent,
                app_name=APP_NAME,
                session_service=sessions,
            )
        return live_runner

    async def _ensure_session(session_id: str) -> str:
        sid = session_id.strip() or str(uuid.uuid4())
        existing = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=sid
        )
        if existing is None:
            created = await sessions.create_session(
                app_name=APP_NAME, user_id="ae", session_id=sid
            )
            return created.id
        return existing.id

    @app.get("/api/workspace")
    async def workspace() -> dict:
        return workspace_catalog()

    @app.get("/api/dashboard")
    async def dashboard(
        geos: str = "",
        boats: str = "",
        opps: str = "",
        sizes: str = "",
        stages: str = "",
        windows: str = "",
    ) -> dict:
        from ui.dashboard import dashboard_payload

        def split(raw: str) -> list[str]:
            return [part.strip() for part in raw.split(",") if part.strip()]

        return dashboard_payload(
            geos=split(geos),
            boats=split(boats),
            opps=split(opps),
            sizes=split(sizes),
            stages=split(stages),
            windows=split(windows),
        )

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        session = await sessions.create_session(app_name=APP_NAME, user_id="ae")
        return {"session_id": session.id, **_context_from_state(session.state)}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        session = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session.id, **_context_from_state(session.state)}

    async def _chat_stream(
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list | None = None,
    ) -> AsyncIterator[str]:
        seen_status: set[str] = set()
        final_text = ""
        emitted = ""
        thought_emitted = ""
        show_reasoning = _ui_reasoning_enabled()
        chunks: list[dict[str, Any]] = []
        last_decision: Any = None
        write_debug_log(
            "chat_start",
            {"session_id": session_id, "message": visible},
        )
        yield _sse({"type": "prompt", "text": visible})
        parts = [types.Part.from_text(text=message)]
        for item in inline or []:
            parts.append(
                types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
            )
        try:
            async for event in _runner().run_async(
                user_id="ae",
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=parts,
                ),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                author = event.author or ""
                label = status_for_author(author)
                if label and label not in seen_status:
                    seen_status.add(label)
                    yield _sse({"type": "status", "label": label})
                text = _streamable_text(event)
                chunk = _event_chunk(event)
                chunks.append(chunk)
                write_debug_log("gemini_chunk", chunk)
                decision = _state_delta(event).get("domain_decision")
                if decision is not None:
                    last_decision = decision
                if show_reasoning:
                    thought = _event_thought(event)
                    if thought:
                        if thought == thought_emitted:
                            thought_add = ""
                        elif thought.startswith(thought_emitted):
                            thought_add = thought[len(thought_emitted) :]
                            thought_emitted = thought
                        elif thought_emitted and thought_emitted in thought:
                            idx = thought.index(thought_emitted) + len(thought_emitted)
                            thought_add = thought[idx:]
                            thought_emitted = thought
                        elif thought_emitted and thought in thought_emitted:
                            thought_add = ""
                        else:
                            thought_add = thought
                            thought_emitted = (
                                f"{thought_emitted}\n\n{thought}"
                                if thought_emitted
                                else thought
                            )
                        if thought_add:
                            yield _sse(
                                {
                                    "type": "reasoning",
                                    "kind": "thought",
                                    "text": thought_add,
                                }
                            )
                if not text:
                    continue
                if emitted and not text.startswith(emitted) and text != emitted:
                    yield _sse({"type": "reset"})
                    emitted = ""
                if text.startswith(emitted):
                    addition = text[len(emitted) :]
                elif text == emitted:
                    addition = ""
                else:
                    addition = text
                emitted = text
                final_text = text
                if not addition:
                    continue
                if event.partial:
                    yield _sse({"type": "delta", "text": addition})
                    continue
                for chunk in word_deltas(addition):
                    yield _sse({"type": "delta", "text": chunk})
        except Exception as exc:
            write_debug_log(
                "chat_error",
                {
                    "session_id": session_id,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                    "chunks": chunks,
                },
            )
            log.exception("chat stream failed")
            yield _sse(
                {
                    "type": "error",
                    "message": "I couldn't complete that request. Try again.",
                    "detail": type(exc).__name__,
                }
            )
            return

        write_debug_log(
            "chat_done",
            {
                "session_id": session_id,
                "chunk_count": len(chunks),
                "chunks": chunks,
                "domain_decision": last_decision,
                "final_text": final_text,
            },
        )
        if final_text:
            yield _sse({"type": "reply", **parse_reply(final_text)})
        else:
            yield _sse(
                {
                    "type": "error",
                    "message": "I didn't get an answer back. Try that again.",
                }
            )

        session = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=session_id
        )
        if session is not None:
            yield _sse({"type": "context", **_context_from_state(session.state)})
        if show_reasoning:
            yield _sse({"type": "reasoning_done"})
        yield _sse({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        message = body.message.strip()
        selection = FilterSelection()
        if body.filters is not None:
            selection = FilterSelection(
                geos=body.filters.geos,
                boats=body.filters.boats,
                opps=body.filters.opps,
                report_types=body.filters.report_types,
                sizes=body.filters.sizes,
                stages=body.filters.stages,
                windows=body.filters.windows,
            )
        if body.task_id:
            selection = restrict_filters(body.task_id, selection)
        decoded = decode_attachments(
            [item.model_dump() for item in body.attachments]
        )
        if body.task_id and not message:
            try:
                message = compose_task_message(body.task_id, selection)
            except KeyError as exc:
                raise HTTPException(status_code=400, detail="Unknown task") from exc
        elif message:
            if "Working filters:" not in message:
                message = apply_filter_notes(message, selection)
        elif decoded:
            message = "Review the attached files."
        else:
            raise HTTPException(status_code=400, detail="Message is empty")
        filenames = [item.filename for item in decoded]
        visible = message
        if filenames and "Attached" not in visible:
            visible = message.rstrip() + "\n\nAttached: " + ", ".join(filenames)
        message, inline = prompt_and_inline(message, decoded)
        session_id = await _ensure_session(body.session_id)
        return StreamingResponse(
            _chat_stream(session_id, message, visible=visible, inline=inline),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    @app.get("/favicon.ico")
    async def favicon() -> Any:
        return FileResponse(STATIC_DIR / "assets" / "bob.png", media_type="image/png")

    @app.get("/")
    async def home() -> Any:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/dashboard")
    async def dashboard_page() -> Any:
        return FileResponse(STATIC_DIR / "dashboard.html")

    @app.get("/chat")
    async def chat_page() -> Any:
        return FileResponse(STATIC_DIR / "chat.html")

    @app.get("/app")
    async def workspace_page() -> Any:
        return FileResponse(STATIC_DIR / "dashboard.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
