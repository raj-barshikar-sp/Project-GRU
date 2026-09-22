"""FastAPI application for Henry's local dashboard and integrations."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from henry_dsr_agent.orchestrator import HenryOrchestrator
from henry_dsr_agent.tools import BattlecardTool, IntentTool, SFDCTool, ZoomInfoTool

STATIC_DIR = Path(__file__).parent / "static"


class HenryRequest(BaseModel):
    """Flexible request envelope shared by workflow endpoints."""

    model_config = ConfigDict(extra="allow")

    message: str | None = None
    action: str | None = None
    account_id: str | None = None
    territory_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """A free-text seller message plus the context the dashboard has on screen."""

    message: str = Field(min_length=1, max_length=20_000)
    account_id: str | None = None
    action: str | None = None
    action_locked: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


async def _call(method: Callable[..., Any], payload: dict[str, Any]) -> Any:
    """Call a public orchestrator method while supporting model or kwargs contracts."""

    signature = inspect.signature(method)
    candidates = (
        ((), payload),
        ((payload,), {}),
        ((), {"request": payload}),
        ((), {"payload": payload}),
    )
    for args, kwargs in candidates:
        try:
            signature.bind(*args, **kwargs)
        except TypeError:
            continue
        result = method(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return _jsonable(result)
    raise TypeError(f"Unsupported signature for {method.__qualname__}")


async def _dispatch(orchestrator: HenryOrchestrator, workflow: str, payload: dict[str, Any]) -> Any:
    payload = dict(payload)
    context = dict(payload.get("context") or {})
    account_id = payload.get("account_id")
    tool = getattr(orchestrator, "sfdc_tool", None)
    repository = getattr(tool, "_repository", None)
    if account_id and "account" not in context and repository is not None:
        account = next(
            (
                item
                for item in repository.all()
                if str(getattr(item, "id", "")) == str(account_id)
            ),
            None,
        )
        if account is not None:
            context["account"] = account
    if workflow == "deal-risk" and "opportunity" not in context and context.get("account"):
        context["opportunity"] = context["account"]
    if context:
        payload["context"] = context

    if workflow == "accounts" and not payload and repository is not None:
        return _jsonable(repository.all())

    aliases = {
        "territories": ("territories", "get_territories", "list_territories", "territory"),
        "accounts": ("accounts", "get_accounts", "list_accounts", "account"),
        "prospecting": ("prospecting", "prospect", "run_prospecting"),
        "discovery": ("discovery", "discover", "run_discovery"),
        "outreach": ("outreach", "create_outreach", "run_outreach"),
        "deal-risk": ("deal_risk", "assess_deal_risk", "run_deal_risk"),
        "ask": ("ask", "handle_dsr_ask"),
        "chat": ("chat", "process_message", "handle_message"),
    }
    for name in aliases[workflow]:
        method = getattr(orchestrator, name, None)
        if callable(method):
            return await _call(method, payload)

    if workflow in {"accounts", "territories"} and repository is not None:
        records = repository.all()
        if workflow == "territories":
            return sorted({account.territory for account in records})
        territory = payload.get("territory_id") or payload.get("territory")
        if territory and hasattr(tool, "get_accounts_by_territory"):
            records = tool.get_accounts_by_territory(str(territory))
        return _jsonable(records)

    for name in ("run_workflow", "execute_workflow", "run", "execute"):
        method = getattr(orchestrator, name, None)
        if not callable(method):
            continue
        if name == "run":
            message = str(payload.get("message") or {
                "prospecting": "Prioritize prospects by intent score",
                "discovery": "Prepare discovery insights",
                "outreach": "Draft outreach",
                "deal-risk": "Assess deal risk",
                "chat": "Summarize this account",
            }.get(workflow, "Research this account"))
            if workflow != "chat" and workflow.replace("-", " ") not in message.lower():
                message = f"{workflow.replace('-', ' ')}: {message}"
            context = dict(payload.get("context") or {})
            account_id = payload.get("account_id")
            if account_id and "account" not in context:
                tool = getattr(orchestrator, "sfdc_tool", None)
                repository = getattr(tool, "_repository", None)
                if repository is not None:
                    account = next(
                        (
                            account
                            for account in repository.all()
                            if str(getattr(account, "id", "")) == str(account_id)
                        ),
                        None,
                    )
                    if account is not None:
                        context["account"] = account
            if workflow == "deal-risk" and "opportunity" not in context:
                context["opportunity"] = context.get("account", {})
            run_kwargs = {
                key: value
                for key, value in {
                    "account_id": account_id,
                    "opportunity_id": payload.get("opportunity_id"),
                    "context": context,
                }.items()
                if value is not None
            }
            result = method(message, **run_kwargs)
            if inspect.isawaitable(result):
                result = await result
            return _jsonable(result)
        call_payload = {"workflow": workflow, **payload}
        signature = inspect.signature(method)
        candidates = (
            ((workflow, payload), {}),
            ((workflow,), payload),
            ((), call_payload),
            ((call_payload,), {}),
        )
        for args, kwargs in candidates:
            try:
                signature.bind(*args, **kwargs)
            except TypeError:
                continue
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return _jsonable(result)
    raise HTTPException(status_code=501, detail=f"Workflow '{workflow}' is not available")


def build_orchestrator() -> HenryOrchestrator:
    """Build Henry with the bundled local enterprise-data adapters."""

    return HenryOrchestrator(
        sfdc_tool=SFDCTool(),
        intent_tool=IntentTool(),
        zoominfo_tool=ZoomInfoTool(),
        battlecard_tool=BattlecardTool(),
    )


def create_app(orchestrator: HenryOrchestrator | None = None) -> FastAPI:
    application = FastAPI(
        title="Henry DSR Agent",
        description="Local-first digital sales workflows for account teams.",
        version="0.1.0",
    )
    application.state.orchestrator = orchestrator or build_orchestrator()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "henry-dsr-agent"}

    async def run(request: Request, workflow: str, payload: dict[str, Any]) -> Any:
        try:
            result = await _dispatch(request.app.state.orchestrator, workflow, payload)
            return {"workflow": workflow, "result": result}
        except HTTPException:
            raise
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            detail = f"Henry could not complete the request: {exc}"
            raise HTTPException(status_code=500, detail=detail) from exc

    @application.get("/api/territories", tags=["workflows"])
    async def get_territories(request: Request) -> Any:
        return await run(request, "territories", {})

    @application.post("/api/territories", tags=["workflows"])
    async def post_territories(request: Request, payload: HenryRequest) -> Any:
        return await run(request, "territories", payload.model_dump(exclude_none=True))

    @application.get("/api/accounts", tags=["workflows"])
    async def get_accounts(request: Request) -> Any:
        return await run(request, "accounts", {})

    @application.post("/api/accounts", tags=["workflows"])
    async def post_accounts(request: Request, payload: HenryRequest) -> Any:
        return await run(request, "accounts", payload.model_dump(exclude_none=True))

    @application.get("/api/accounts/{account_id}/quick-view", tags=["workflows"])
    async def account_quick_view(request: Request, account_id: str) -> Any:
        """Return the CRM, intent, technology, contact, and risk snapshot."""
        method = getattr(request.app.state.orchestrator, "account_quick_view", None)
        if not callable(method):
            raise HTTPException(status_code=501, detail="Account quick view is not available")
        try:
            result = method(account_id)
            if inspect.isawaitable(result):
                result = await result
            return {"result": _jsonable(result)}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/ask-catalog", tags=["workflows"])
    async def ask_catalog(request: Request) -> Any:
        return await request.app.state.orchestrator.ask_catalog()

    def workflow_route(workflow: str) -> Callable[..., Any]:
        async def endpoint(request: Request, payload: HenryRequest) -> Any:
            return await run(request, workflow, payload.model_dump(exclude_none=True))

        return endpoint

    for workflow in ("prospecting", "discovery", "outreach", "deal-risk", "ask"):
        application.add_api_route(
            f"/api/{workflow}",
            workflow_route(workflow),
            methods=["POST"],
            tags=["workflows"],
            name=workflow,
        )

    @application.post("/api/chat", tags=["chat"])
    async def chat(request: Request, payload: ChatRequest) -> Any:
        return await run(request, "chat", payload.model_dump(exclude_none=True))

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
