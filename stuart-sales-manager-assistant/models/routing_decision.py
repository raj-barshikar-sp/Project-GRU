"""Orchestrator routing decision models.

Routing is decided by the planner LLM. This module only parses and validates
what the model returns, so a hallucinated or renamed agent can never run.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agents.orchestrator.prompt import TASK_AGENT_IDS


class AgentRoute(BaseModel):
    """One task specialist the orchestrator should invoke."""

    agent_id: str = Field(
        description="Task specialist to run. Synthesis is not a routing target."
    )
    reason: str = Field(
        default="",
        description="Why this specialist is needed for the current query.",
    )
    focus: str = Field(
        default="",
        description="Account, territory, or topic the specialist should focus on.",
    )


class RoutingDecision(BaseModel):
    """Task specialists selected for a user query.

    Synthesis is not listed here. The orchestrator calls synthesis after
    every task specialist finishes.
    """

    agents: list[AgentRoute] = Field(
        default_factory=list,
        description=(
            "Task specialists to run in order. Empty means the turn needs no "
            "grounded records and direct_reply answers it."
        ),
    )
    direct_reply: str = Field(
        default="",
        description=(
            "Stuart's own words when agents is empty: greetings, small talk, "
            "scope questions, and clarifications. Ignored when agents is set."
        ),
    )

    @classmethod
    def from_state(cls, raw: Any) -> RoutingDecision:
        """Parse a routing payload from session state, JSON, or model text."""
        if raw is None or raw == "":
            return cls()
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            return cls.from_text(raw)
        if isinstance(raw, dict):
            return cls._from_mapping(raw)
        try:
            return cls.model_validate(raw)
        except ValidationError:
            return cls()

    @classmethod
    def from_text(cls, text: str) -> RoutingDecision:
        """Parse JSON or agent ids embedded in model text."""
        payload = _extract_json_object(text)
        if isinstance(payload, dict):
            parsed = cls._from_mapping(payload)
            if parsed.agents or parsed.direct_reply:
                return parsed
        found = [
            {"agent_id": agent_id}
            for agent_id in TASK_AGENT_IDS
            if re.search(rf"\b{agent_id}\b", text)
        ]
        if found:
            return cls._from_mapping({"agents": found})
        return cls()

    @classmethod
    def _from_mapping(cls, raw: dict[str, Any]) -> RoutingDecision:
        routes: list[dict[str, Any]] = []
        for item in raw.get("agents") or []:
            if isinstance(item, str) and item in TASK_AGENT_IDS:
                routes.append({"agent_id": item})
                continue
            if not isinstance(item, dict):
                continue
            agent_id = item.get("agent_id") or item.get("id") or item.get("name")
            if agent_id in TASK_AGENT_IDS:
                routes.append(
                    {
                        "agent_id": agent_id,
                        "reason": item.get("reason") or "",
                        "focus": item.get("focus") or "",
                    }
                )
        try:
            return cls.model_validate(
                {
                    "agents": routes,
                    "direct_reply": raw.get("direct_reply") or "",
                }
            )
        except ValidationError:
            return cls()


def _extract_json_object(text: str) -> Any | None:
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
