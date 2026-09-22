"""Read-only tools for the ABM orchestrator."""

from __future__ import annotations

import json

from mktg_core import metrics
from mktg_core.connectors import accounts_by_id
from tools.regional_events.events_tools import get_account_snapshot
from tools._shared._common import REGION_HELP, conn, parse_region
from mktg_core.rendering.artifact import describe_saved, save_artifact, save_email_cadence_csv


def get_top_accounts(region: str) -> str:
    """Rank target accounts by ICP fit, intent, engagement and pipeline.

    Use for questions about top accounts, ABM priorities or account tiering.

    Args:
        region: {region_help}

    Returns:
        A markdown table of accounts ranked by composite ABM score.
    """
    return metrics.account_tiering(conn(), parse_region(region)).to_markdown()


def get_account_intel_brief(account_id: str) -> str:
    """Deep-dive intel on one account: CRM, technographics, news and intent.

    Args:
        account_id: Account id such as ACC-001.

    Returns:
        A markdown briefing pack for the account.
    """
    c = conn()
    base = get_account_snapshot(account_id)
    facts = c.enrichment.get_company_facts(account_id.strip())
    tech = c.enrichment.list_technographics([account_id.strip()])

    extra = ["", "**Technographics**", ""]
    if tech:
        extra += ["| Category | Vendor | Status |", "|---|---|---|"]
        for t in tech:
            extra.append(f"| {t.category} | {t.vendor} | {t.status} |")
    else:
        extra.append("No technographic data recorded.")

    if facts:
        extra += ["", "**Business context**", ""]
        if facts.recent_news:
            extra.append(f"- Recent news: {facts.recent_news}")
        if facts.recent_leadership_change:
            extra.append(f"- Leadership: {facts.recent_leadership_change}")
        if facts.strategic_priorities:
            extra.append("- Priorities: " + ", ".join(facts.strategic_priorities))

    return base + "\n" + "\n".join(extra)


def get_gap_value_map(account_id: str) -> str:
    """Map account technology gaps to SailPoint capabilities with quantified ROI.

    Args:
        account_id: Account id such as ACC-001.

    Returns:
        A markdown table of gaps, capabilities and annual value in USD.
    """
    return metrics.gap_value_map(conn(), account_id.strip()).to_markdown()


def get_persona_framework(persona_key: str) -> str:
    """Messaging framework for a buying-committee persona.

    Args:
        persona_key: One of CISO, CIO, IAM_Director, Compliance_Officer, or
            "all" for every persona.

    Returns:
        Persona priorities, pains and messaging guidance.
    """
    personas = conn().kb.list_personas()
    if persona_key.strip().lower() == "all":
        selected = personas
    else:
        key = persona_key.strip()
        selected = [p for p in personas if p.id == key or key in p.title]
    if not selected:
        return f"No persona found for {persona_key!r}."
    lines = []
    for p in selected:
        lines += [
            f"### {p.title} ({p.id})",
            f"**Priorities:** {', '.join(p.priorities)}",
            f"**Pain points:** {', '.join(p.pain_points)}",
            f"**Do:** {', '.join(p.messaging_do)}",
            f"**Avoid / objections:** {', '.join(p.messaging_dont)}",
            "",
        ]
    return "\n".join(lines)


def get_regulatory_context(industry: str, region: str) -> str:
    """Regulatory guides relevant to an industry and region.

    Args:
        industry: Industry name such as Financial Services, or "all".
        region: AMER, EMEA, APJ, or all.

    Returns:
        Applicable regulations and identity-security relevance.
    """
    regs = conn().kb.list_regulations()
    ind = industry.strip().lower()
    reg = parse_region(region)
    lines = ["### Regulatory context", ""]
    for r in regs:
        industries = [i.lower() for i in r.industries]
        if ind not in {"all", ""} and "all" not in industries and ind not in industries:
            continue
        if reg and r.region not in {reg.value, "Global"}:
            continue
        lines += [
            f"**{r.name} ({r.id})** - {r.region}",
            r.summary,
            f"Identity relevance: {r.identity_relevance}",
            "",
        ]
    return "\n".join(lines) if len(lines) > 2 else "No matching regulations found."


def save_abm_artifact(artifact_json: str, artifact_type: str,
                      filename: str) -> str:
    """Save an ABM deliverable (email CSV, LinkedIn, Folloze, playbook).

    Args:
        artifact_json: JSON matching the deliverable shape.
        artifact_type: email_cadence, linkedin, folloze, or playbook.
        filename: Output filename without path.

    Returns:
        Where the file was saved, or an error message.
    """
    result = save_artifact(artifact_json, artifact_type, filename)
    return describe_saved(result)


for _fn in (get_top_accounts,):
    _fn.__doc__ = _fn.__doc__.replace("{region_help}", REGION_HELP)

ABM_TOOLS = [
    get_top_accounts,
    get_account_intel_brief,
    get_gap_value_map,
    get_persona_framework,
    get_regulatory_context,
    save_abm_artifact,
]
