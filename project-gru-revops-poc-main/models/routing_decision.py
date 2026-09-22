"""Orchestrator routing decision models."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agents.book_logic import (
    agent_for_topic,
    domain_tokens,
    route_hints,
    task_tokens,
)
from agents.constants import TASK_AGENT_IDS

_GREETING_HINTS = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "hi there",
    "hey there",
    "hi bob",
    "hey bob",
    "hello bob",
    "yo",
    "howdy",
)
_THANKS_HINTS = (
    "thanks",
    "thank you",
    "thanks bob",
    "thank you bob",
    "thx",
    "ty",
    "cheers",
    "appreciate it",
    "thanks a lot",
    "thanks so much",
    "thank you so much",
    "ok thanks",
    "okay thanks",
)
_ACK_HINTS = (
    "ok",
    "okay",
    "okay great",
    "ok great",
    "okay cool",
    "ok cool",
    "great",
    "cool",
    "nice",
    "perfect",
    "awesome",
    "sweet",
    "got it",
    "sounds good",
    "makes sense",
    "copy that",
    "noted",
    "will do",
    "all good",
    "all right",
    "alright",
    "yes",
    "yep",
    "yeah",
    "yup",
    "no",
    "nope",
    "nah",
    "k",
    "kk",
    "lol",
    "haha",
    "wow",
    "hmm",
    "nice one",
    "good to know",
    "that works",
    "that helps",
    "thats helpful",
    "that's helpful",
)
_CAPABILITY_HINTS = (
    "help",
    "what can you do",
    "what do you do",
    "who are you",
    "who are you bob",
    "what are you",
    "how can you help",
)
_FOLLOW_UP_HINTS = (
    "that account",
    "same one",
    "same account",
    "my book",
    "that deal",
    "this deal",
    "the opp",
    "that opp",
    "this account",
    "for this",
    "on this",
    "what about",
    "and also",
    "same for",
    "go deeper",
    "more detail",
    "say more",
    "explain that",
    "walk me through",
    "longer email",
    "email artifact",
    "make the email",
    "rewrite the email",
    "draft an email",
)
_DEICTIC_RE = re.compile(
    r"\b(this|that|it|its|them|those|the quote|the deal|the account|the opp)\b"
)
_ARTIFACT_RE = re.compile(
    r"\b(e-?mails?|mails?|notes?|slack|recipients?|letter|artifacts?)\b"
    r"|\b(draft|write|send|compose|make|rewrite|create)\b.{0,80}\b"
    r"(people|team|owner|csm|note|mail|artifact)"
    r"|\bconcerned\b.{0,48}\bpeople\b"
    r"|\bpeople\b.{0,32}\bconcerned\b"
)
_OFF_DOMAIN_RE = re.compile(
    r"\b("
    r"jokes?|funny|riddle|pun|limerick|"
    r"weather|temperature outside|"
    r"sports?|football|nba|mlb|nhl|"
    r"recipe|cook dinner|"
    r"capital of|who won the|"
    r"netflix|song lyrics"
    r")\b"
)
_ACTION_FOLLOW_RE = re.compile(
    r"\b("
    r"next steps?|what should i do|what should we do|"
    r"what do i do|what do we do|how do i proceed|"
    r"what(?:'s| is) next|recommended actions?|"
    r"action items?|where do i start|what should be my next"
    r")\b"
)


def _token_routes(lowered: str) -> list[dict[str, str]]:
    return [
        {"agent_id": agent_id, "reason": "follow-up intent match"}
        for agent_id, tokens in domain_tokens().items()
        if any(re.search(rf"\b{re.escape(token)}\b", lowered) for token in tokens)
    ]


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
            "Task specialists to run in order. Empty means no specialist "
            "is needed (greeting or off-topic)."
        ),
    )
    direct_reply: str = Field(
        default="",
        description="Short reply when agents is empty. Ignored when agents is set.",
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


class DomainDecision(BaseModel):
    """Root router pick: one RevOps team, a clarifying question, or a greeting."""

    domain_id: str = Field(
        default="",
        description=(
            "One domain orchestrator id such as forecast_orchestrator. "
            "Empty when asking a clarifying question or greeting."
        ),
    )
    clarifying_question: str = Field(
        default="",
        description="One question when the team is genuinely ambiguous.",
    )
    direct_reply: str = Field(
        default="",
        description="Greeting or off-topic reply. Empty when domain_id is set.",
    )

    @classmethod
    def from_state(cls, raw: Any) -> DomainDecision:
        if raw is None or raw == "":
            return cls()
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, str):
            payload = _extract_json_object(raw)
            if isinstance(payload, dict):
                raw = payload
            else:
                return cls()
        if not isinstance(raw, dict):
            try:
                return cls.model_validate(raw)
            except ValidationError:
                return cls()
        domain_id = (
            raw.get("domain_id")
            or raw.get("domainId")
            or raw.get("domain")
            or raw.get("team")
            or ""
        )
        return cls(
            domain_id=str(domain_id),
            clarifying_question=str(
                raw.get("clarifying_question") or raw.get("clarifyingQuestion") or ""
            ),
            direct_reply=str(
                raw.get("direct_reply") or raw.get("directReply") or ""
            ),
        )



def _cleaned(query: str) -> str:
    return re.sub(r"[^\w\s]", "", query.lower()).strip()


def _is_greeting(query: str) -> bool:
    return _cleaned(query) in _GREETING_HINTS


def _is_thanks(query: str) -> bool:
    return _cleaned(query) in _THANKS_HINTS


def _is_ack(query: str) -> bool:
    cleaned = _cleaned(query)
    if cleaned in _ACK_HINTS:
        return True
    words = cleaned.split()
    if 1 <= len(words) <= 4 and all(
        word in _ACK_HINTS or word in {"bob", "great", "cool", "nice"}
        for word in words
    ):
        return True
    return False


def _is_capability(query: str) -> bool:
    return _cleaned(query) in _CAPABILITY_HINTS


def _account_mentions(lowered: str) -> bool:
    from agents.data.crm import ACCOUNTS

    for name, row in ACCOUNTS.items():
        if name.lower() in lowered:
            return True
        for alias in row.get("aliases") or []:
            if alias.lower() in lowered:
                return True
    return False


_STAGE_RE = re.compile(r"ss\s?\d{2}")
_STAGE_ASK_RE = re.compile(
    r"\b("
    r"difference|vs\.?|versus|compare|between|"
    r"what(?:'s| is)|what does|what comes|meaning of|define|explain|"
    r"after|before|next|following|prior|comes after|"
    r"stages?|sequence|order"
    r")\b"
)
_STAGE_WORK_RE = re.compile(
    r"\b("
    r"check|confirm|inspect|blocking|stuck|"
    r"quote by|primary quote|hygiene|forecast|kpis?|rollup"
    r")\b"
)


def is_stage_glossary(query: str) -> bool:
    """True for stage-map questions with no account to look up."""
    lowered = query.lower()
    if _account_mentions(lowered) or re.search(r"\bopp-\d+\b", lowered):
        return False
    if _STAGE_WORK_RE.search(lowered):
        return False
    has_code = bool(_STAGE_RE.search(lowered))
    talks_stages = bool(re.search(r"\bstages?\b", lowered))
    if has_code and _STAGE_ASK_RE.search(lowered):
        return True
    return bool(
        talks_stages
        and re.search(r"\b(what|which|list|after|before|next|explain|all)\b", lowered)
    )


def is_finding_follow_up(query: str) -> bool:
    """True for short asks about the last briefing, not a new RevOps task."""
    if _is_ack(query) or _is_thanks(query) or _is_greeting(query):
        return False
    return bool(
        re.search(
            r"\b("
            r"crucial|critical|urgent|serious|material|blocking|"
            r"matter|worry|ignore|priority|"
            r"how bad|how serious|how urgent|"
            r"is (it|that|this) (bad|ok|okay|fine|a problem|an issue)|"
            r"does (it|that|this) matter|"
            r"should i (worry|care|act|fix|flag)|"
            r"what does that mean|why is that"
            r")\b",
            query.lower(),
        )
    )


def is_off_domain(query: str) -> bool:
    """True for asks with no RevOps reading — jokes, weather, sports, trivia."""
    return bool(_OFF_DOMAIN_RE.search(query.lower()))


def is_action_follow_up(query: str) -> bool:
    """True when the AE wants next steps from the last briefing."""
    if _is_ack(query) or _is_thanks(query) or _is_greeting(query):
        return False
    return bool(_ACTION_FOLLOW_RE.search(query.lower()))


def is_mail_follow_up(query: str) -> bool:
    """True when the AE wants a paste-ready note from the last briefing."""
    if _is_ack(query) or _is_thanks(query) or _is_greeting(query):
        return False
    return bool(_ARTIFACT_RE.search(query.lower()))


def is_context_follow_up(query: str) -> bool:
    """True for follow-ups that should reuse the last account and specialist."""
    if (
        is_finding_follow_up(query)
        or is_mail_follow_up(query)
        or is_action_follow_up(query)
    ):
        return True
    lowered = query.lower()
    if any(hint in lowered for hint in _FOLLOW_UP_HINTS):
        return True
    return bool(_DEICTIC_RE.search(lowered))


def looks_like_revops_task(
    query: str,
    *,
    last_account: str = "",
    last_agent: str = "",
    last_topic: str = "",
) -> bool:
    """True when the AE is asking Bob to do book work, including follow-ups."""
    if is_stage_glossary(query):
        return False
    if is_off_domain(query):
        return False
    if last_account or last_agent or last_topic:
        return True
    lowered = query.lower()
    if any(
        hint in lowered for hints in route_hints().values() for hint in hints
    ):
        return True
    if any(hint in lowered for hint in _FOLLOW_UP_HINTS):
        return True
    if any(token in lowered for token in task_tokens()):
        return True
    if re.search(r"\bopp-\d+\b", lowered):
        return True
    return _account_mentions(lowered)


def heuristic_route(
    query: str,
    *,
    last_account: str = "",
    last_territory: str = "",
    last_opportunity: str = "",
    last_agent: str = "",
    last_topic: str = "",
) -> RoutingDecision:
    """Deterministic specialist picks; the planner model writes any chat reply."""
    text = query.strip()
    if not text:
        return RoutingDecision()

    lowered = text.lower()
    if (
        is_stage_glossary(text)
        or _is_thanks(text)
        or _is_greeting(text)
        or _is_capability(text)
        or _is_ack(text)
        or is_off_domain(text)
    ):
        return RoutingDecision()

    routes = [
        {"agent_id": agent_id, "reason": "explicit intent match"}
        for agent_id, hints in route_hints().items()
        if any(hint in lowered for hint in hints)
    ]

    if routes:
        if any(route["agent_id"].startswith("revops_") for route in routes):
            routes = [
                route
                for route in routes
                if route["agent_id"].startswith("revops_")
            ]
        return RoutingDecision.from_state({"agents": routes})

    if last_account or last_territory or last_opportunity or last_agent or last_topic:
        token_routes = _token_routes(lowered)
        if token_routes:
            if any(route["agent_id"].startswith("revops_") for route in token_routes):
                token_routes = [
                    route
                    for route in token_routes
                    if route["agent_id"].startswith("revops_")
                ]
            return RoutingDecision.from_state({"agents": token_routes})
        reused = (
            last_agent
            if last_agent.startswith("revops_")
            else agent_for_topic(last_topic)
        )
        if reused:
            return RoutingDecision.from_state(
                {
                    "agents": [
                        {
                            "agent_id": reused,
                            "reason": "follow-up on last briefing",
                        }
                    ]
                }
            )

    return RoutingDecision()


def enforce_explicit_routes(
    query: str, planned: RoutingDecision
) -> RoutingDecision:
    """Prefer deterministic explicit intents, otherwise trust the planner."""
    explicit = heuristic_route(query)
    if explicit.agents:
        return explicit
    return RoutingDecision.from_state(planned)


def producer_domain_for(agent_ids: list[str]) -> str:
    """Pick the domain that produces facts other teams would consume."""
    from agents.orchestrator.domains import DOMAIN_ORDER, SPECIALIST_DOMAIN

    domains = {
        SPECIALIST_DOMAIN[item] for item in agent_ids if item in SPECIALIST_DOMAIN
    }
    for domain in DOMAIN_ORDER:
        if domain in domains:
            return domain
    return ""


def specialists_in_domain(
    domain_id: str, matched: list[str] | None = None
) -> list[str]:
    from agents.orchestrator.domains import DOMAIN_SPECIALISTS

    allowed = list(DOMAIN_SPECIALISTS.get(domain_id, ()))
    if matched:
        overlap = [item for item in matched if item in allowed]
        if overlap:
            return overlap
    return allowed


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
