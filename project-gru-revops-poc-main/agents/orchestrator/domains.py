"""RevOps domain orchestrators — no tools; descriptions are the routing logic."""

from __future__ import annotations

from agents.specialists.forecast.agent import revops_forecast_agent
from agents.specialists.hygiene.agent import revops_hygiene_agent
from agents.specialists.otc.agent import revops_otc_agent
from agents.specialists.pricing.agent import revops_pricing_agent
from agents.specialists.quoting.agent import revops_quoting_agent
from agents.specialists.reporting.agent import revops_reporting_agent
from agents.specialist_factory import make_domain_orchestrator

_DOMAIN_INSTRUCTION = """
You are a RevOps domain orchestrator. You have no tools and you never answer
from general knowledge. Transfer to exactly one specialist child whose
description matches the request. If two children could apply, pick the one
that produces the facts the other would need. If it is genuinely ambiguous,
ask one clarifying question instead of guessing.
""".strip()

forecast_orchestrator = make_domain_orchestrator(
    name="forecast_orchestrator",
    description=(
        "Forecasting team. Verbal call / Rev Intel, call vs CRM roll-up, "
        "pipeline cover, large-deal backup, CRM score, pacing vs conversion, "
        "and weekly forecast updates. Not quotes, decks, credit, or pricing."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_forecast_agent],
)

quoting_orchestrator = make_domain_orchestrator(
    name="quoting_orchestrator",
    description=(
        "Quoting team. Forecast value on the quote, SS20/SS40 primary quote, "
        "deal desk rules, quote errors, carve notes, agentic attach, special "
        "terms, and quote vs floor deviations. Not regional forecast call "
        "numbers, OTC credit, or QBR decks."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_quoting_agent],
)

reporting_orchestrator = make_domain_orchestrator(
    name="reporting_orchestrator",
    description=(
        "Reporting team. Weekly/monthly/quarterly KPIs, KPI decks, forecast "
        "review packs, pipeline review packs, metrics Q&A, and QBR decks. "
        "Not live quote edits, credit holds, or deal-desk validation."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_reporting_agent],
)

hygiene_orchestrator = make_domain_orchestrator(
    name="hygiene_orchestrator",
    description=(
        "Hygiene team. Inspect expected fields, forecast participation, "
        "stage-complete hygiene, and updated notes. Not quote pricing, "
        "credit/ARR, or building a deck."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_hygiene_agent],
)

otc_orchestrator = make_domain_orchestrator(
    name="otc_orchestrator",
    description=(
        "Order-to-cash team. Credit and ARR calculator, order review/hygiene, "
        "aging receivables, and churn impact tied to CSM. One-shot OTC "
        "lookups stay on this team. Not forecast calls or quote structure."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_otc_agent],
)

pricing_orchestrator = make_domain_orchestrator(
    name="pricing_orchestrator",
    description=(
        "Pricing analytics team. Deal score, money left on the table, deal "
        "architect levers, and waterfall vs floor. Not creating the quote, "
        "credit holds, or weekly verbal call."
    ),
    instruction=_DOMAIN_INSTRUCTION,
    sub_agents=[revops_pricing_agent],
)

DOMAIN_AGENTS = (
    forecast_orchestrator,
    quoting_orchestrator,
    reporting_orchestrator,
    hygiene_orchestrator,
    otc_orchestrator,
    pricing_orchestrator,
)

DOMAIN_SPECIALISTS: dict[str, tuple[str, ...]] = {
    "forecast_orchestrator": ("revops_forecast",),
    "quoting_orchestrator": ("revops_quoting",),
    "reporting_orchestrator": ("revops_reporting",),
    "hygiene_orchestrator": ("revops_hygiene",),
    "otc_orchestrator": ("revops_otc",),
    "pricing_orchestrator": ("revops_pricing",),
}

SPECIALIST_DOMAIN = {
    specialist: domain
    for domain, specialists in DOMAIN_SPECIALISTS.items()
    for specialist in specialists
}

# Producer teams first when a request spans two domains.
DOMAIN_ORDER = (
    "hygiene_orchestrator",
    "forecast_orchestrator",
    "quoting_orchestrator",
    "otc_orchestrator",
    "pricing_orchestrator",
    "reporting_orchestrator",
)
