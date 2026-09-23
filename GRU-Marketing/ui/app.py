"""FastAPI app that streams the marketing orchestrator to the workspace UI."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event, EventActions
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mktg_core.contracts.marketing_ops import UPLOADED_LEAD_FILES_STATE
from pydantic import BaseModel, Field

from ui.attachments import decode_attachments, prompt_and_inline, uploaded_csv_rows
from ui.briefing import parse_reply
from ui.catalog import (
    FilterSelection,
    apply_filter_notes,
    apply_write_facts,
    compose_task_message,
    expand_account_follow_up,
    filter_tag_items,
    merge_mentioned_accounts,
    task_id_from_message,
    workspace_catalog,
    write_guard_reply,
)
from ui.chats import ChatStore
from ui.collections import CollectionStore
from ui.progress import THINKING_LABEL, status_for_author
from ui.scope import OFF_TOPIC_REPLY, is_in_scope, social_reply
from ui.stream import word_deltas
from ui.trace import RunTrace, tracing_enabled

APP_NAME = "marketing-agents"
STATIC_DIR = Path(__file__).with_name("static")
SESSION_KEYS = ("last_account", "last_region", "last_campaign", "last_event")
USER_ID = "marketer"
# Thoughts only arrive while the model is still working if the run streams.
# Without this they land in one lump per turn and the Thinking panel jumps
# from empty to finished.
RUN_CONFIG = RunConfig(streaming_mode=StreamingMode.SSE)


def _error_detail(exc: Exception) -> str:
    """Detail to ride along on an error event, without changing the user copy.

    The chat stream always shows a generic apology; this is the machine-facing
    hint next to it. By default it is just the exception type, which is safe to
    surface. Setting MKTG_DEBUG_ERRORS adds the message, turning a bare
    "ValueError" into "ValueError: no session for id ..." when debugging a run.
    """
    if os.environ.get("MKTG_DEBUG_ERRORS"):
        message = str(exc).strip()
        return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
    return type(exc).__name__


class ChatFilters(BaseModel):
    geos: list[str] = Field(default_factory=list)
    campaigns: list[str] = Field(default_factory=list)
    campaign_types: list[str] = Field(default_factory=list)
    asset_types: list[str] = Field(default_factory=list)
    content: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)


class ChatAttachment(BaseModel):
    filename: str = ""
    mime_type: str = ""
    content_base64: str = ""


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = ""
    chat_id: str = ""
    task_id: str = ""
    turn_id: str = ""
    collection_id: str = ""
    pinned: bool = False
    filters: ChatFilters | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


class ChatPatch(BaseModel):
    pinned: bool | None = None
    collection_id: str | None = None
    title: str | None = None


class CollectionWrite(BaseModel):
    name: str = ""


def _event_text(event: Event, *, thoughts: bool = False) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text
        for part in event.content.parts
        if getattr(part, "text", None)
        and bool(getattr(part, "thought", False)) is thoughts
    )


def _squashed(text: str) -> str:
    """Whitespace-free form, for comparing a chunk against what we have."""
    return "".join(text.split())


def _merge_thought(blocks: list[str], chunk: str) -> str:
    """Fold one event's thought text into the transcript built so far.

    A streaming run hands the thinking over a few words at a time and then
    repeats the whole turn on its aggregated event, so appending every chunk
    would say everything twice. One block per model turn, joined by a blank
    line, which is the break the client reads as a new paragraph.
    """
    current = blocks[-1]
    seen, arriving = _squashed(current), _squashed(chunk)
    if not seen.endswith(arriving):
        blocks[-1] = chunk if arriving.startswith(seen) else current + chunk
    return "\n\n".join(blocks)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _context_from_state(state: Any) -> dict[str, str]:
    return {key: str(state.get(key) or "") for key in SESSION_KEYS}


def _selection_from_filters(filters: ChatFilters | None) -> FilterSelection:
    if filters is None:
        return FilterSelection()
    return FilterSelection(
        campaigns=filters.campaigns,
        campaign_types=filters.campaign_types,
        asset_types=filters.asset_types,
        content=filters.content,
        events=filters.events,
        accounts=filters.accounts,
        geos=filters.geos,
    )


def _filters_payload(selection: FilterSelection) -> dict[str, list[str]]:
    return {
        "campaigns": list(selection.campaigns),
        "campaign_types": list(selection.campaign_types),
        "asset_types": list(selection.asset_types),
        "content": list(selection.content),
        "events": list(selection.events),
        "accounts": list(selection.accounts),
    }


def _has_filters(selection: FilterSelection) -> bool:
    return any(_filters_payload(selection).values()) or bool(selection.geos)


def _history_title(text: str) -> str:
    compact = " ".join(text.split())
    return f"{compact[:41]}…" if len(compact) > 42 else compact or "Chat"


class _ChatJob:
    """One model run that outlives the browser's SSE connection."""

    def __init__(self, chat_id: str, turn_id: str) -> None:
        self.chat_id = chat_id
        self.turn_id = turn_id
        self.events: list[dict[str, Any]] = []
        self.queues: list[asyncio.Queue[dict[str, Any]]] = []
        self.task: asyncio.Task[None] | None = None

    def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        for queue in list(self.queues):
            queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        for event in self.events:
            queue.put_nowait(event)
        self.queues.append(queue)
        return queue


def create_app(
    *,
    runner: Any | None = None,
    session_service: InMemorySessionService | None = None,
    chat_store: ChatStore | None = None,
    collection_store: CollectionStore | None = None,
) -> FastAPI:
    """Build the UI app. Tests inject a fake runner so Gemini is not required."""

    sessions = session_service or InMemorySessionService()
    store = chat_store or ChatStore()
    folders = collection_store or CollectionStore()
    live_runner = runner
    in_scope_sessions: set[str] = set()
    jobs: dict[str, _ChatJob] = {}
    background: set[asyncio.Task] = set()
    app = FastAPI(title="GRU Marketing", docs_url=None, redoc_url=None)

    def _runner() -> Any:
        nonlocal live_runner
        if live_runner is None:
            from dotenv import load_dotenv

            # `adk web` reads .env for you; running uvicorn directly does not.
            load_dotenv(Path(__file__).resolve().parent.parent / ".env")

            # One builder for every entry point: the shared app carries the
            # context cache and reply-contract plugin, and we only hand it the
            # session service the UI keeps its context in.
            from root.app import build_runner

            live_runner = build_runner(APP_NAME, session_service=sessions)
        return live_runner

    async def _ensure_session(session_id: str) -> str:
        sid = session_id.strip() or str(uuid.uuid4())
        existing = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=sid
        )
        if existing is None:
            created = await sessions.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=sid
            )
            return created.id
        return existing.id

    @app.get("/api/workspace")
    async def workspace() -> dict:
        return workspace_catalog()

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        session = await sessions.create_session(
            app_name=APP_NAME, user_id=USER_ID
        )
        return {"session_id": session.id, **_context_from_state(session.state)}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        session = await sessions.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session.id, **_context_from_state(session.state)}

    @app.get("/api/chats")
    async def list_chats() -> dict[str, list[dict]]:
        return {"chats": store.list_chats()}

    @app.get("/api/chats/{chat_id}")
    async def read_chat(chat_id: str) -> dict:
        record = store.get(chat_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown chat")
        job = jobs.get(chat_id)
        record["running"] = bool(job and job.task is not None and not job.task.done())
        return record

    def _cancel_job(chat_id: str) -> bool:
        job = jobs.get(chat_id)
        if job is not None and job.task is not None and not job.task.done():
            job.task.cancel()
            return True
        record = store.get(chat_id)
        if record is None:
            return False
        turns = record.get("turns") or []
        last = turns[-1] if turns else {}
        if last.get("reply") is None and last.get("status") == "pending":
            store.finish_reply(
                chat_id,
                {"kind": "error", "text": "Stopped. James cancelled this reply."},
                last.get("id") or "",
                status="cancelled",
            )
        return True

    @app.patch("/api/chats/{chat_id}")
    async def patch_chat(chat_id: str, body: ChatPatch) -> dict:
        if store.get(chat_id) is None:
            raise HTTPException(status_code=404, detail="Unknown chat")
        fields = body.model_fields_set
        collection_id = body.collection_id
        if "collection_id" in fields and collection_id:
            if folders.get(collection_id) is None:
                raise HTTPException(status_code=404, detail="Unknown collection")
        payload: dict[str, Any] = {}
        if "pinned" in fields:
            payload["pinned"] = body.pinned
        if "collection_id" in fields:
            payload["collection_id"] = collection_id
        if "title" in fields:
            title = (body.title or "").strip()
            if not title:
                raise HTTPException(status_code=400, detail="Name is empty")
            payload["title"] = title[:80]
        if not payload:
            return store.get(chat_id)
        record = store.patch_chat(chat_id, **payload)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown chat")
        return store.get(chat_id) or record

    @app.delete("/api/chats/{chat_id}")
    async def remove_chat(chat_id: str) -> dict[str, bool]:
        _cancel_job(chat_id)
        jobs.pop(chat_id, None)
        if not store.delete(chat_id):
            raise HTTPException(status_code=404, detail="Unknown chat")
        return {"ok": True}

    @app.get("/api/collections")
    async def list_collections() -> dict[str, list[dict]]:
        return {"collections": folders.list_collections()}

    @app.post("/api/collections")
    async def create_collection(body: CollectionWrite) -> dict:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is empty")
        return folders.create(name)

    @app.patch("/api/collections/{collection_id}")
    async def rename_collection(collection_id: str, body: CollectionWrite) -> dict:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is empty")
        record = folders.rename(collection_id, name)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        return record

    @app.delete("/api/collections/{collection_id}")
    async def remove_collection(collection_id: str) -> dict[str, bool]:
        if folders.get(collection_id) is None:
            raise HTTPException(status_code=404, detail="Unknown collection")
        store.clear_collection(collection_id)
        folders.delete(collection_id)
        return {"ok": True}

    @app.post("/api/chats/{chat_id}/cancel")
    async def cancel_chat(chat_id: str) -> dict[str, bool]:
        if store.get(chat_id) is None and chat_id not in jobs:
            raise HTTPException(status_code=404, detail="Unknown chat")
        _cancel_job(chat_id)
        return {"ok": True}

    def _spawn(coro: Any) -> asyncio.Task[None]:
        task = asyncio.create_task(coro)
        background.add(task)
        task.add_done_callback(background.discard)
        return task

    async def _subscribe_stream(
        job: _ChatJob,
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list | None = None,
        skip_model: bool = False,
        canned_reply: str = OFF_TOPIC_REPLY,
    ) -> AsyncIterator[str]:
        # Start the model from the stream, not the request coroutine. A task
        # spawned from the endpoint can be torn down when the handler returns,
        # which left the UI on "James is thinking…" with no reply.
        if job.task is None or job.task.done():
            job.task = _spawn(
                _run_job(
                    job,
                    session_id,
                    message,
                    visible=visible,
                    inline=inline,
                    skip_model=skip_model,
                    canned_reply=canned_reply,
                )
            )
        queue = job.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if job.task is None or not job.task.done():
                        continue
                    while True:
                        try:
                            leftover = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            yield _sse({"type": "done"})
                            return
                        yield _sse(leftover)
                        if leftover.get("type") == "done":
                            return
                yield _sse(event)
                if event.get("type") == "done":
                    return
        finally:
            if queue in job.queues:
                job.queues.remove(queue)

    async def _run_job(
        job: _ChatJob,
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list | None = None,
        skip_model: bool = False,
        canned_reply: str = OFF_TOPIC_REPLY,
    ) -> None:
        chat_id = job.chat_id
        turn_id = job.turn_id
        closed = False

        def emit(event: dict[str, Any]) -> None:
            nonlocal closed
            job.publish(event)
            if event.get("type") == "done":
                closed = True
            if event.get("type") == "status":
                store.patch_turn(
                    chat_id, turn_id, status_label=event.get("label") or ""
                )
            elif event.get("type") == "reasoning":
                store.patch_turn(
                    chat_id, turn_id, reasoning=event.get("text") or ""
                )

        def fail(message_text: str, *, status: str = "error", detail: str = "") -> None:
            error: dict[str, Any] = {"type": "error", "message": message_text}
            if detail:
                error["detail"] = detail
            store.finish_reply(
                chat_id,
                {"kind": "error", "text": message_text},
                turn_id,
                status=status,
            )
            emit(error)
            emit({"type": "done"})

        seen_status: set[str] = set()
        final_text = ""
        emit({"type": "prompt", "text": visible})
        try:
            if skip_model:
                payload = parse_reply(canned_reply)
                store.finish_reply(chat_id, payload, turn_id)
                emit({"type": "reply", **payload})
                emit({"type": "done"})
                return
            # The first ADK event can be seconds away. Claim the line straight away
            # so the wait starts with real copy instead of the client placeholder,
            # and seed seen_status so the root's own event does not repeat it.
            seen_status.add(THINKING_LABEL)
            emit({"type": "status", "label": THINKING_LABEL})
            parts = [types.Part.from_text(text=message)]
            for item in inline or []:
                parts.append(
                    types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
                )
            trace = RunTrace(label=visible[:48]) if tracing_enabled() else None
            thought_blocks: list[str] = []
            thinking_turn = False
            thinking_sent = ""
            try:
                async for event in _runner().run_async(
                    user_id=USER_ID,
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=parts,
                    ),
                    run_config=RUN_CONFIG,
                ):
                    author = event.author or ""
                    label = status_for_author(author)
                    if label and label not in seen_status:
                        seen_status.add(label)
                        emit({"type": "status", "label": label})
                    thought = _event_text(event, thoughts=True)
                    if thought.strip():
                        if not thinking_turn:
                            thought_blocks.append("")
                            thinking_turn = True
                        thinking = _merge_thought(thought_blocks, thought)
                        if thinking != thinking_sent:
                            thinking_sent = thinking
                            emit(
                                {
                                    "type": "reasoning",
                                    "kind": "thought",
                                    "text": thinking,
                                }
                            )
                    # A complete event closes the turn it summarised, so the next
                    # thought starts a paragraph of its own.
                    if not event.partial:
                        thinking_turn = False
                    text = _event_text(event)
                    # Marked before the empty-text skip below, because a routing
                    # hop emits only a function call and that is the cost we are
                    # trying to see.
                    if trace is not None:
                        trace.mark(author, len(text) + len(thought))
                    if not text.strip():
                        continue
                    if event.is_final_response():
                        final_text = text
            except asyncio.CancelledError:
                if trace is not None:
                    trace.log()
                fail(
                    "Stopped. James cancelled this reply.",
                    status="cancelled",
                    detail="CancelledError",
                )
                raise
            except Exception as exc:
                if trace is not None:
                    trace.log()
                fail(
                    "I couldn't complete that request. Try again.",
                    detail=_error_detail(exc),
                )
                return

            if trace is not None:
                trace.log()

            if final_text:
                # Only reveal the final answer. Specialist events can contain JSON
                # and internal details that must never flash in the chat stream.
                payload = parse_reply(final_text)
                store.finish_reply(chat_id, payload, turn_id)
                # Structured kinds land as finished cards. Streaming the raw text
                # here would spell out markdown first and throw it away.
                if payload["kind"] == "plain":
                    for chunk in word_deltas(payload["text"]):
                        emit({"type": "delta", "text": chunk})
                        if job.queues:
                            await asyncio.sleep(0.008)
                emit({"type": "reply", **payload})
            else:
                fail("I didn't get an answer back. Try that again.")
                return

            session = await sessions.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id
            )
            if session is not None:
                emit({"type": "context", **_context_from_state(session.state)})
            emit({"type": "reasoning_done"})
            emit({"type": "done"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            fail(
                "I couldn't complete that request. Try again.",
                detail=_error_detail(exc),
            )
        finally:
            if not closed:
                emit({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        message = body.message.strip()
        selection = merge_mentioned_accounts(
            _selection_from_filters(body.filters), message
        )
        decoded = decode_attachments(
            [item.model_dump() for item in body.attachments]
        )
        if body.task_id and not message:
            try:
                message = compose_task_message(body.task_id, selection)
            except KeyError as exc:
                raise HTTPException(status_code=400, detail="Unknown task") from exc
        elif message:
            pass
        elif decoded:
            message = "Review the attached files."
        else:
            raise HTTPException(status_code=400, detail="Message is empty")
        filenames = [item.filename for item in decoded]
        visible = message
        if filenames and "Attached" not in visible:
            visible = message.rstrip() + "\n\nAttached: " + ", ".join(filenames)
        session_id = await _ensure_session(body.session_id)
        chat_id = body.chat_id.strip() or str(uuid.uuid4())
        prior = store.get(chat_id)
        task_id = (body.task_id or "").strip() or task_id_from_message(visible)
        if not task_id and prior:
            task_id = str(prior.get("task_id") or "")
        previous_in_scope = session_id in in_scope_sessions
        if prior:
            previous_in_scope = previous_in_scope or bool(prior.get("in_scope"))
            last = (prior.get("turns") or [{}])[-1]
            if (last.get("reply") or {}).get("kind") == "question":
                previous_in_scope = True
        if selection.accounts:
            message = expand_account_follow_up(message, task_id, selection)
        record = store.append_user(
            chat_id=chat_id,
            session_id=session_id,
            title=_history_title(visible),
            user=visible,
            tags=filter_tag_items(selection),
            filters=_filters_payload(selection),
            task_id=task_id,
            turn_id=body.turn_id,
            collection_id=body.collection_id,
            pinned=body.pinned,
        )
        turn_id = body.turn_id.strip() or str(
            (record.get("turns") or [{}])[-1].get("id") or ""
        )
        csv_files = uploaded_csv_rows(decoded)
        if csv_files:
            session = await sessions.get_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=session_id
            )
            if session is not None:
                await sessions.append_event(
                    session,
                    Event(
                        author="workspace_upload",
                        invocation_id=f"upload-{uuid.uuid4()}",
                        actions=EventActions(
                            state_delta={UPLOADED_LEAD_FILES_STATE: csv_files}
                        ),
                    ),
                )
        small_talk = social_reply(visible)
        guard = write_guard_reply(visible, selection)
        if guard:
            # The composer filled a reminder, not a create. Running the model
            # still produced a mocked segment from invented accounts.
            skip_model = True
            canned = guard
        elif small_talk:
            # Small talk neither opens nor closes marketing context: a "thanks"
            # between two pipeline questions must not strand the follow-up.
            skip_model = True
            canned = small_talk
        else:
            skip_model = not is_in_scope(
                visible,
                task_id=task_id,
                has_attachments=bool(decoded),
                has_filters=_has_filters(selection),
                previous_turn_in_scope=previous_in_scope,
            )
            canned = OFF_TOPIC_REPLY
        keep_scope = (not skip_model) or bool(guard)
        if not small_talk:
            if keep_scope:
                in_scope_sessions.add(session_id)
            else:
                in_scope_sessions.discard(session_id)
            store.patch_chat(chat_id, in_scope=keep_scope, task_id=task_id)
        # Filters stay out of the composer text. They still travel with the
        # model prompt so specialists see the selected marketing context.
        if not skip_model:
            message = apply_filter_notes(message, selection)
            message = apply_write_facts(message, task_id, selection)
        message, inline = prompt_and_inline(message, decoded)
        previous = jobs.get(chat_id)
        if previous is not None and previous.task is not None and not previous.task.done():
            previous.task.cancel()
        job = _ChatJob(chat_id, turn_id)
        jobs[chat_id] = job
        return StreamingResponse(
            _subscribe_stream(
                job,
                session_id,
                message,
                visible=visible,
                inline=inline,
                skip_model=skip_model,
                canned_reply=canned,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
                "X-Chat-Id": chat_id,
            },
        )

    def _page(name: str) -> FileResponse:
        # Both shells pin CSS/JS with a build query. Revalidating the HTML
        # prevents an old page from requesting stale assets.
        return FileResponse(
            STATIC_DIR / name,
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/dashboard")
    async def dashboard(
        geos: str = "",
        spend: str = "",
        types: str = "",
        windows: str = "",
    ) -> dict:
        from ui.dashboard import dashboard_payload

        def split(raw: str) -> list[str]:
            return [part.strip() for part in raw.split(",") if part.strip()]

        return dashboard_payload(
            geos=split(geos),
            spend=split(spend),
            types=split(types),
            windows=split(windows),
        )

    @app.get("/api/decks/{filename}")
    async def download_deck(filename: str) -> Any:
        name = Path(filename).name
        if name != filename or ".." in filename or not name.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail="Invalid deck file")
        from mktg_core.rendering.deck import OUTPUT_DIR as DECK_DIR

        root = DECK_DIR.resolve()
        path = (DECK_DIR / name).resolve()
        if root not in path.parents and path != root:
            raise HTTPException(status_code=400, detail="Invalid deck file")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Deck not found")
        return FileResponse(
            path,
            filename=name,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation"
            ),
        )

    @app.get("/favicon.ico")
    async def favicon() -> Any:
        return FileResponse(STATIC_DIR / "assets" / "favicon.ico")

    @app.get("/")
    async def home() -> Any:
        return _page("index.html")

    @app.get("/app")
    async def workspace_page() -> Any:
        return _page("dashboard.html")

    @app.get("/dashboard")
    async def dashboard_page() -> Any:
        return _page("dashboard.html")

    @app.get("/chat")
    async def chat_alias() -> Any:
        return _page("chat.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
