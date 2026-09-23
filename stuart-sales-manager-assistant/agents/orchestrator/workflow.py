"""Gemini planner → JSON-grounded specialists → conversational Stuart reply."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from agents.activity import log_activity, preview
from agents.constants import CHILD_TIMEOUT_SECONDS, FALLBACK_REPLY
from agents.orchestrator.prompt import TASK_AGENT_IDS
from agents.session_memory import SESSION_KEYS, seed_context_from_text
from models.routing_decision import RoutingDecision
from models.synthesis_output import SynthesisOutput, render_synthesis_markdown


def _content(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def _event_text(event: Event) -> str:
    parts = (event.content.parts if event.content else None) or []
    return "\n".join(part.text for part in parts if getattr(part, "text", None))


def _user_text(ctx: InvocationContext) -> str:
    parts = (ctx.user_content.parts if ctx.user_content else None) or []
    return "\n".join(part.text for part in parts if getattr(part, "text", None))


_CHITCHAT = re.compile(
    r"""^(?:hi+|hello|hey+|yo|howdy|gm|
        good\s*(?:morning|afternoon|evening)|
        thanks?(?:\s+you)?|thx|ty|cheers|
        how(?:'s|\s+are)\s+you(?:\s+doing)?|
        what'?s\s+up)
        (?:\s+(?:there|stuart|team|again))*
        [\s!.?,]*$""",
    re.IGNORECASE | re.VERBOSE,
)
_THANKS = re.compile(r"thank|thx|^ty\b|cheers", re.IGNORECASE)


def chitchat_reply(text: str) -> str | None:
    """Answer greetings locally so Gemini is never called for 'hi'."""
    visible = text.split("\n\nWorking filters:", 1)[0].strip()
    if not visible or len(visible) > 60 or not _CHITCHAT.match(visible):
        return None
    if _THANKS.search(visible):
        return "Anytime. What should we look at next?"
    return "Hi — what should we review?"


def _parse_payload(events: list[Event]) -> Any:
    for event in reversed(events):
        if event.output is not None:
            output = event.output
            return output.model_dump() if hasattr(output, "model_dump") else output
        text = _event_text(event).strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return None


def _final_event(author: str, ctx: InvocationContext, text: str) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)],
        ),
    )


class StuartWorkflow(BaseAgent):
    """Let Gemini orchestrate while code enforces source and agent boundaries."""

    planner_agent: Agent
    specialist_agents: dict[str, BaseAgent] = {}
    final_writer_agent: Agent

    def model_post_init(self, __context: Any) -> None:
        specialists = dict(self.specialist_agents)
        for child in self.sub_agents:
            if child.name in TASK_AGENT_IDS:
                specialists[child.name] = child
        object.__setattr__(self, "specialist_agents", specialists)

    def _child_ctx(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
    ) -> InvocationContext:
        return ctx.model_copy(
            update={
                "user_content": _content(request),
                "branch": (
                    f"{ctx.branch}.{self.name}.{agent.name}"
                    if ctx.branch
                    else f"{self.name}.{agent.name}"
                ),
            }
        )

    async def _run_child(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
    ) -> tuple[list[Event], Any, str]:
        events: list[Event] = []
        error = ""
        started = time.perf_counter()
        log_activity("child.start", agent=agent.name)
        try:
            async with asyncio.timeout(CHILD_TIMEOUT_SECONDS):
                async for event in agent.run_async(self._child_ctx(agent, ctx, request)):
                    events.append(event)
        except TimeoutError:
            error = f"Timeout after {CHILD_TIMEOUT_SECONDS}s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        log_activity(
            "child.failed" if error else "child.done",
            agent=agent.name,
            error=error,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            level=logging.INFO if error else logging.DEBUG,
        )
        return events, _parse_payload(events), error

    @staticmethod
    def _working_context(state: Any) -> dict[str, str]:
        return {key: str(state.get(key) or "") for key in SESSION_KEYS}

    def _planner_request(self, query: str, state: Any) -> str:
        return json.dumps(
            {
                "message": query,
                "working_context": self._working_context(state),
            },
            ensure_ascii=False,
        )

    def _specialist_request(self, name: str, query: str, state: Any) -> str:
        return json.dumps(
            {
                "manager_message": query,
                "working_context": self._working_context(state),
                "specialist": name,
            },
            ensure_ascii=False,
        )

    def _writer_request(
        self,
        query: str,
        state: Any,
        reports: dict[str, Any],
    ) -> str:
        return json.dumps(
            {
                "original_question": query,
                "working_context": self._working_context(state),
                "specialist_reports": reports,
            },
            ensure_ascii=False,
            default=str,
        )

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        query = _user_text(ctx).strip()
        state = ctx.session.state
        for key in SESSION_KEYS:
            state.setdefault(key, "")
        seed_context_from_text(state, query)
        log_activity("turn.start", invocation=ctx.invocation_id, query=preview(query))

        cheap = chitchat_reply(query)
        if cheap:
            log_activity("route.chitchat", specialists=[])
            yield _final_event(self.name, ctx, cheap)
            return

        planner_events, raw_plan, planner_error = await self._run_child(
            self.planner_agent,
            ctx,
            self._planner_request(query, state),
        )
        for event in planner_events:
            yield event
        plan = RoutingDecision.from_state(raw_plan)
        selected = list(
            dict.fromkeys(
                route.agent_id
                for route in plan.agents
                if route.agent_id in self.specialist_agents
            )
        )
        log_activity(
            "route.planner",
            specialists=selected,
            error=planner_error,
        )

        if not selected:
            reply = plan.direct_reply.strip() or FALLBACK_REPLY
            yield _final_event(self.name, ctx, reply)
            return

        async def run(name: str) -> tuple[str, list[Event], Any, str]:
            events, payload, error = await self._run_child(
                self.specialist_agents[name],
                ctx,
                self._specialist_request(name, query, state),
            )
            return name, events, payload, error

        reports: dict[str, Any] = {}
        pending = [asyncio.create_task(run(name)) for name in selected]
        for finished in asyncio.as_completed(pending):
            name, events, payload, error = await finished
            for event in events:
                yield event
            reports[name] = (
                payload
                if payload is not None
                else {"status": "error", "error": error or "No report returned."}
            )
            log_activity(
                "specialist.done" if payload is not None else "specialist.failed",
                specialist=name,
                error=error,
            )

        writer_events, raw_response, writer_error = await self._run_child(
            self.final_writer_agent,
            ctx,
            self._writer_request(query, state, reports),
        )
        for event in writer_events:
            yield event
        try:
            briefing = SynthesisOutput.model_validate(raw_response)
            reply = render_synthesis_markdown(briefing) if briefing.summary.strip() else ""
        except Exception:
            reply = ""
        if not reply:
            reply = (
                "I couldn't turn those findings into a reliable briefing. "
                "Try the question once more."
            )
        log_activity(
            "turn.done",
            specialists=selected,
            error=writer_error,
            chars=len(reply),
        )
        yield _final_event(self.name, ctx, reply)
