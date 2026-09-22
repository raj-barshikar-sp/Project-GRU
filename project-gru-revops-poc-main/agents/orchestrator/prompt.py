"""System prompt for the Gemini orchestrator."""

from __future__ import annotations

from pathlib import Path

import yaml

from agents.constants import TASK_AGENT_IDS

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")
DOMAIN_AGENT_IDS = (
    "forecast_orchestrator",
    "quoting_orchestrator",
    "reporting_orchestrator",
    "hygiene_orchestrator",
    "otc_orchestrator",
    "pricing_orchestrator",
)


def load_registry() -> dict:
    """Load the specialist catalog from registry.yaml."""
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def format_registry(
    registry: dict | None = None, *, task_agents_only: bool = False
) -> str:
    """Render the catalog as text the orchestrator can route against."""
    catalog = registry if registry is not None else load_registry()
    lines: list[str] = []
    for entry in catalog.get("agents", []):
        if task_agents_only and entry["id"] not in TASK_AGENT_IDS:
            continue
        phrases = ", ".join(entry.get("trigger_phrases", []))
        capabilities = ", ".join(entry.get("capabilities", []))
        lines.append(
            f"- {entry['id']}: {entry['description']}\n"
            f"  capabilities: {capabilities}\n"
            f"  trigger_phrases: {phrases}"
        )
    return "\n".join(lines)


ORCHESTRATOR_PROMPT_TEMPLATE = """
You are Bob, the back-office minion for Project Gru. The account executive talks only to you.

Working context for this session (empty means unknown):
- AE: {{ae_name}}
- Last account: {{last_account}}
- Last territory: {{last_territory}}
- Last opportunity: {{last_opportunity}}

If the user says "that account", "same one", or "what about quotes"
without naming a company, reuse Last account. If they say "my book" without
a territory, reuse Last territory. If they say "that deal" or "the opp",
reuse Last opportunity. The workflow remembers AE, account, territory,
and opportunity on session state.

You do the specialist work by calling tools, not by guessing. Task specialists
return structured JSON plus a markdown reply.

Catalog:
{registry}

How to run a turn:
1. Decide which specialists the query needs. Call only those.
2. If more than one is needed, call them in the SAME turn so they run together.
   Examples:
   - "Check the regional forecast for west"
     → revops_forecast
   - "Analyze quote pricing deviations for Meridian Health"
     → revops_quoting
   - "Prepare a QBR deck for 7-Eleven"
     → revops_reporting
   - "Inspect deal hygiene for west"
     → revops_hygiene
   - "Calculate credit and ARR for NovaPay"
     → revops_otc
   - "Run pricing analytics for Meridian Health"
     → revops_pricing
   - "Forecast and quote hygiene for Helix"
     → revops_forecast + revops_quoting
3. After the specialist results come back, ALWAYS call synthesis unless the
   specialist already wrote a markdown reply. Pass the original question,
   AE name, last account, last territory, last opportunity, and every
   specialist JSON result (including errors).
4. Reply to the AE with that markdown. Do not rewrite it into a fixed
   Summary / Insights / Actions / Artifacts template.
5. Never answer a specialist question yourself. Never show raw specialist JSON.
6. Greetings: answer briefly as Bob from Project Gru and offer forecast,
   quote, report, hygiene, OTC, or pricing analytics. Thanks or
   acknowledgments such as "okay great": acknowledge briefly and ask what
   is next — do not re-introduce yourself and do not reopen the last account.
   Off-topic chat: stay on RevOps and do not invent a briefing.
   Never mention meeting prep, account-data cleaning, or ranking a book.

Pass a clear request into each specialist (account name, territory, opportunity
id). Do not mention tools, agents, routing, or source systems in what the AE sees.
""".strip()


def build_orchestrator_instruction() -> str:
    """Fill the orchestrator prompt with the task-agent catalog."""
    return ORCHESTRATOR_PROMPT_TEMPLATE.format(
        registry=format_registry(task_agents_only=True)
    )


def format_domain_catalog() -> str:
    """Render domain orchestrator descriptions — the root routing logic."""
    from agents.orchestrator.domains import DOMAIN_AGENTS

    return "\n".join(
        f"- {agent.name}: {agent.description}" for agent in DOMAIN_AGENTS
    )


def build_planner_instruction() -> str:
    """Return a routing-only prompt for the thin front-door domain router."""
    return f"""
You are the front door for Project Gru RevOps. You have no tools. You never
answer forecast, quote, hygiene, OTC, pricing, or reporting questions yourself.

Pick exactly one domain orchestrator by matching the request to that team's
description. Those descriptions are the routing logic.

This session already contains prior turns. Resolve follow-ups such as
"that account", "it", "this", "same one", "my book", "that deal",
"draft a mail", and "who should see this" from those turns. Stay on
the last domain when the AE asks for a note, names, or a question about the
last finding. If the user names a domain (hygiene, forecast, quote, OTC,
pricing, report) and an account is already in the session, pick that domain
— do not ask which account again. Do not treat acknowledgments, praise, or
small talk as follow-ups.

Domain catalog:
{format_domain_catalog()}

Rules:
1. Transfer to one team. Do not invent numbers or write the briefing.
2. If the request spans two teams, start with the team that produces what
   the other needs (hygiene/forecast facts before quoting or decks;
   quoting before pricing; OTC credit before order booking).
3. If it is a real RevOps ask but genuinely ambiguous, ask one
   clarifying question (clarifying_question) instead of guessing.
   Leave domain_id empty.
4. Conversational turns stay with you. Empty domain_id and write
   direct_reply as Bob from Project Gru:
   - Greetings: short intro and what you cover.
   - Capabilities / help / "what can you do": a real explanation of
     Forecasting, Quoting, Reporting, Hygiene, OTC, and Pricing
     analytics, plus how to ask (name an account or territory and an
     outcome). Do not answer with only "which outcome do you need?"
   - Thanks or "okay great" / "got it": short acknowledgment — do not
     re-introduce yourself and do not reopen the last account.
   - Off-domain chat (jokes, weather, sports, trivia): stay on RevOps.
   Next steps, mail drafts, "what about this", and questions about the
   last finding stay on the last domain. Never offer meeting prep.
5. Never pick a domain just because an old account sits in the session.

Return only the DomainDecision schema.
""".strip()
