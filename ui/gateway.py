"""Single browser shell that proxies requests to isolated role runtimes."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).with_name("static")
ROLES = {
    "bob": {
        "name": "Bob",
        "title": "Bob the Back Office Minion",
        "role": "RevOps",
        "url": os.getenv("GRU_BOB_URL", "http://127.0.0.1:8091"),
    },
    "james": {
        "name": "James",
        "title": "James the Marketing Assistant",
        "role": "Marketing",
        "url": os.getenv("GRU_JAMES_URL", "http://127.0.0.1:8092"),
    },
    "stuart": {
        "name": "Stuart",
        "title": "Stuart the Sales Manager Assistant",
        "role": "Sales Manager",
        "url": os.getenv("GRU_STUART_URL", "http://127.0.0.1:8093"),
    },
    "henry": {
        "name": "Henry",
        "title": "Henry the DSR Minion",
        "role": "DSR",
        "url": os.getenv("GRU_HENRY_URL", "http://127.0.0.1:8094"),
    },
}


def _role(value: str) -> str:
    role = value.strip().lower() or "bob"
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")
    return role


def _upstream(role: str, path: str) -> str:
    return f"{ROLES[role]['url']}{path}"


def create_app(*, client: httpx.AsyncClient | None = None) -> FastAPI:
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0))
    owns_client = client is None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if owns_client:
            await http.aclose()

    app = FastAPI(
        title="Project GRU",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    async def proxy(
        method: str,
        role: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        try:
            response = await http.request(
                method,
                _upstream(role, path),
                params=params,
                content=content,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"{ROLES[role]['name']} is not available.",
            ) from exc
        forwarded = {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "x-session-id", "x-chat-id"}
        }
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=forwarded,
        )

    @app.get("/api/roles")
    async def roles() -> dict[str, Any]:
        return {
            "roles": [
                {"id": role_id, **{k: v for k, v in config.items() if k != "url"}}
                for role_id, config in ROLES.items()
            ]
        }

    @app.get("/api/workspace")
    async def workspace(role: str = "bob") -> Response:
        return await proxy("GET", _role(role), "/api/workspace")

    @app.get("/api/dashboard")
    async def dashboard(request: Request, role: str = "bob") -> Response:
        selected = _role(role)
        if selected != "bob":
            raise HTTPException(
                status_code=404,
                detail="The dashboard is available for Bob only.",
            )
        params = {key: value for key, value in request.query_params.items() if key != "role"}
        return await proxy("GET", selected, "/api/dashboard", params=params)

    @app.post("/api/session")
    async def new_session(role: str = "bob") -> Response:
        return await proxy("POST", _role(role), "/api/session")

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str, role: str = "bob") -> Response:
        return await proxy("GET", _role(role), f"/api/session/{session_id}")

    @app.post("/api/chat")
    async def chat(request: Request) -> StreamingResponse:
        try:
            body = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
        selected = _role(str(body.pop("role", "bob")))
        upstream_request = http.build_request(
            "POST",
            _upstream(selected, "/api/chat"),
            content=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        try:
            upstream = await http.send(upstream_request, stream=True)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"{ROLES[selected]['name']} is not available.",
            ) from exc

        async def chunks():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()

        headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() in {"cache-control", "x-accel-buffering", "x-session-id", "x-chat-id"}
        }
        return StreamingResponse(
            chunks(),
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "text/event-stream"),
            headers=headers,
        )

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        icon = STATIC_DIR / "assets" / "bob.png"
        if icon.exists():
            return FileResponse(icon, media_type="image/png")
        return Response(status_code=204)

    @app.get("/")
    async def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/dashboard")
    async def dashboard_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "dashboard.html")

    @app.get("/chat")
    async def chat_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "chat.html")

    @app.get("/app")
    async def workspace_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "dashboard.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
