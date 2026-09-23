"""Gemini orchestration with injected JSON context."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions.session import Session
from google.genai import types

from agents.orchestrator.workflow import StuartWorkflow, chitchat_reply


def _ctx(query: str) -> InvocationContext:
    return InvocationContext.model_construct(
        session_service=object(),
        invocation_id="inv",
        session=Session(id="s", app_name="agents", user_id="u", state={}),
        user_content=types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)],
        ),
    )


def _workflow() -> StuartWorkflow:
    specialists = {
        "crm_intelligence_specialist": SimpleNamespace(
            name="crm_intelligence_specialist"
        )
    }
    return StuartWorkflow.model_construct(
        name="central_orchestrator",
        planner_agent=SimpleNamespace(name="route_planner"),
        specialist_agents=specialists,
        final_writer_agent=SimpleNamespace(name="synthesis"),
        sub_agents=[],
    )


async def _collect(workflow: StuartWorkflow, query: str) -> str:
    text = []
    async for event in workflow._run_async_impl(_ctx(query)):
        if event.author == "central_orchestrator" and event.content:
            text.extend(
                part.text
                for part in event.content.parts or []
                if getattr(part, "text", None)
            )
    return "\n".join(text)


def test_hi_skips_the_planner() -> None:
    workflow = _workflow()
    calls = []

    async def fake(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        return [], {"agents": [], "direct_reply": "should not run"}, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    assert asyncio.run(_collect(workflow, "hi")) == "Hi — what should we review?"
    assert asyncio.run(_collect(workflow, "thanks!")) == (
        "Anytime. What should we look at next?"
    )
    assert calls == []
    assert chitchat_reply("hi, how's my forecast") is None


def test_planner_direct_reply_is_the_chat_response() -> None:
    workflow = _workflow()
    calls = []

    async def fake(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        return [], {"agents": [], "direct_reply": "Morning — what are we reviewing?"}, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    assert asyncio.run(_collect(workflow, "what can you do?")) == (
        "Morning — what are we reviewing?"
    )
    assert calls == ["route_planner"]


def test_specialist_report_reaches_writer() -> None:
    workflow = _workflow()
    requests = {}

    async def fake(agent, ctx, request):  # noqa: ANN001
        requests[agent.name] = request
        if agent.name == "route_planner":
            return [], {
                "agents": [{"agent_id": "crm_intelligence_specialist"}]
            }, ""
        if agent.name == "crm_intelligence_specialist":
            return [], {
                "answer": "There are 19 open opportunities.",
                "facts": ["Global Logistics Corp is owned by Sarah Jenkins."],
            }, ""
        return [], {
            "summary": "You have 19 open opportunities.",
            "insights": ["Global Logistics Corp is owned by Sarah Jenkins."],
            "actions": [{"action": "Review the largest deal.", "due": "Friday"}],
        }, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    reply = asyncio.run(_collect(workflow, "What are my deals?"))
    assert reply.startswith("## Summary\nYou have 19 open opportunities.")
    assert "## Key Insights\n- Global Logistics Corp is owned by Sarah Jenkins." in reply
    assert "1. Review the largest deal. (owner: you, when: Friday)" in reply
    assert "## Artifacts\nNone." in reply
    assert "What are my deals?" in requests["crm_intelligence_specialist"]
    assert "There are 19 open opportunities." in requests["synthesis"]


def test_unknown_agent_id_never_runs() -> None:
    workflow = _workflow()
    calls = []

    async def fake(agent, ctx, request):  # noqa: ANN001
        calls.append(agent.name)
        return [], {
            "agents": [{"agent_id": "old_forecasting_agent"}],
            "direct_reply": "What part of the forecast should we inspect?",
        }, ""

    workflow._run_child = fake  # type: ignore[method-assign]
    reply = asyncio.run(_collect(workflow, "forecast"))
    assert "forecast" in reply
    assert calls == ["route_planner"]


def test_specialist_request_contains_no_tool_protocol() -> None:
    request = _workflow()._specialist_request(
        "crm_intelligence_specialist",
        "List my deals.",
        {},
    )
    assert "manager_message" in request
    assert "Tool scope" not in request
