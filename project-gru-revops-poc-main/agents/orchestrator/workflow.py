"""Code-owned turn: planner, specialists, then synthesis (no LLM tool choreography)."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types

from agents.book_logic import (
    account_geo,
    account_people,
    empty_book_briefing,
    join_names,
)
from ui.debug_log import write as write_debug_log
from agents.constants import CHILD_TIMEOUT_SECONDS
from agents.data.runtime import REVOPS_AGENT_IDS, execute_revops
from agents.orchestrator.prompt import TASK_AGENT_IDS
from agents.session_memory import (
    SESSION_KEYS,
    apply_working_context,
    detect_account_in_text,
    detect_opportunity_in_text,
    detect_territory_in_text,
    seed_context_from_text,
)
from agents.synthesis.payload import build_synthesis_request
from models.routing_decision import (
    DomainDecision,
    _extract_json_object,
    is_action_follow_up,
    is_finding_follow_up,
    is_mail_follow_up,
    specialists_in_domain,
)
from models.synthesis_output import (
    CopyReadyArtifact,
    RecommendedAction,
    SynthesisOutput,
    strip_email_signoff,
    validate_synthesis_output,
)

_INTERNAL_TERMS = (
    *TASK_AGENT_IDS,
    "forecast_orchestrator",
    "quoting_orchestrator",
    "reporting_orchestrator",
    "hygiene_orchestrator",
    "otc_orchestrator",
    "pricing_orchestrator",
    "orchestrator",
    "synthesis",
    "single_turn",
    "remember_working_context",
    "route_planner",
)


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(
        role="user", parts=[genai_types.Part.from_text(text=text)]
    )


def _event_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text
        for part in event.content.parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


def _joined_event_text(events: list[Event]) -> str:
    for event in reversed(events):
        if getattr(event, "partial", False):
            continue
        text = _event_text(event).strip()
        if text:
            return text
    return "\n".join(
        text for event in events if (text := _event_text(event).strip())
    ).strip()


def _specialist_replies(results: dict[str, Any]) -> list[str]:
    replies: list[str] = []
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("reply") or "").strip()
        if text:
            replies.append(text)
    return replies


def _user_text(ctx: InvocationContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return "\n".join(
        part.text
        for part in ctx.user_content.parts
        if getattr(part, "text", None)
    )


def _parse_payload(events: list[Event]) -> Any:
    chunks: list[str] = []
    for event in reversed(events):
        delta = getattr(getattr(event, "actions", None), "state_delta", None) or {}
        if delta.get("domain_decision") is not None:
            return delta["domain_decision"]
        if event.output is not None:
            return event.output
        text = _event_text(event).strip()
        if text:
            chunks.append(text)
            parsed = _extract_json_object(text)
            if parsed is not None:
                return parsed
    if chunks:
        from models.routing_decision import DomainDecision

        planned = DomainDecision.from_state("".join(reversed(chunks)))
        if planned.domain_id or planned.direct_reply or planned.clarifying_question:
            return planned
    return None


def _record_counts(results: dict[str, Any]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for name, payload in results.items():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        counts[name] = {
            str(table): len(rows) if isinstance(rows, list) else 1
            for table, rows in records.items()
        }
    return counts


def _working_delta(state: Any) -> dict[str, str]:
    return {key: str(state.get(key) or "") for key in SESSION_KEYS}


def _final_event(
    author: str,
    ctx: InvocationContext,
    text: str,
    *,
    partial: bool = False,
) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        partial=partial,
        state=_working_delta(ctx.session.state),
        content=genai_types.Content(
            role="model", parts=[genai_types.Part.from_text(text=text)]
        ),
    )


def _named_account(payload: dict[str, Any], records: dict[str, Any]) -> str:
    for item in payload.get("accounts") or []:
        name = str(item).strip()
        if name:
            return name
    for key in ("Quote", "Opportunity"):
        for row in records.get(key) or []:
            if isinstance(row, dict) and row.get("account"):
                return str(row["account"])
    for item in payload.get("quotes") or []:
        parts = str(item).split(" ", 1)
        if len(parts) == 2 and parts[1].strip():
            return parts[1].strip()
    return ""


def _quote_forecast_amount(row: dict[str, Any]) -> float:
    raw = row.get("forecast_value")
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _owner_for(account: str) -> str:
    people = account_people(account)
    return people[0] if people else "team"


def _first_named_row(
    records: dict[str, Any], key: str, account: str
) -> dict[str, Any]:
    for row in records.get(key) or []:
        if not isinstance(row, dict):
            continue
        if not account or str(row.get("account") or "") in {"", account}:
            return row
    return {}


def _opportunity_for(account: str, records: dict[str, Any]) -> dict[str, Any]:
    row = _first_named_row(records, "Opportunity", account)
    if row:
        return row
    from agents.data.dummy_store import load_opportunities

    for opp in load_opportunities().values():
        if opp.get("account") == account:
            return dict(opp)
    return {}


def _health_for(account: str, records: dict[str, Any]) -> dict[str, Any]:
    row = _first_named_row(records, "AccountHealth", account)
    if row:
        return row
    from agents.data.dummy_store import load_account_health

    return dict(load_account_health().get(account) or {})


def _email_log_for(account: str, records: dict[str, Any]) -> dict[str, Any]:
    row = _first_named_row(records, "EmailLog", account)
    if row:
        return row
    from agents.data.dummy_store import load_email_log

    return dict(load_email_log().get(account) or {})


def _roles_for(account: str, records: dict[str, Any]) -> list[str]:
    roles = [
        str(row.get("role_name") or "").strip()
        for row in (records.get("ContactRole") or [])
        if isinstance(row, dict)
        and str(row.get("account") or "") in {"", account}
        and str(row.get("role_name") or "").strip()
    ]
    if roles:
        return list(dict.fromkeys(roles))
    from agents.data.dummy_store import load_contact_roles

    return list(load_contact_roles().get(account) or [])


def _money(amount: float) -> str:
    return f"${int(amount):,}"


def _first_name(full: str) -> str:
    token = str(full or "").strip().split()
    return token[0] if token else "there"


def _pretty_sku(name: str) -> str:
    raw = str(name or "").strip()
    if raw.lower() in {"capped ps", "capped professional services"}:
        return "Capped Professional Services"
    return raw


def _join_scope(parts: list[str]) -> str:
    clean = [part for part in parts if part]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def _customer_first_name(account: str, hint: str) -> str:
    from agents.data.crm import CONTACTS

    contacts = CONTACTS.get(account) or []
    blob = hint.lower()
    for row in contacts:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        if name.lower() in blob or _first_name(name).lower() in blob.split():
            return _first_name(name)
    for role in ("User buyer", "Champion", "Economic buyer"):
        for row in contacts:
            if str(row.get("role") or "") == role and row.get("name"):
                return _first_name(str(row["name"]))
    if contacts and contacts[0].get("name"):
        return _first_name(str(contacts[0]["name"]))
    return "there"


def _quote_rows_from_results(
    results: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        quotes = [
            row
            for row in (records.get("Quote") or [])
            if isinstance(row, dict)
        ]
        if quotes:
            return quotes, records if isinstance(records, dict) else {}
    return [], {}


def _quote_mail_artifact(
    who: str,
    quote: dict[str, Any],
    records: dict[str, Any],
) -> CopyReadyArtifact:
    opp = _opportunity_for(who, records)
    hint = " ".join(
        str(part)
        for part in (
            opp.get("next_step"),
            opp.get("manager_notes"),
            " ".join(str(item) for item in (quote.get("quote_errors") or [])),
            " ".join(str(item) for item in (quote.get("validation_error_codes") or [])),
        )
        if part
    )
    to = _customer_first_name(who, hint)
    qid = str(quote.get("quote_id") or "").strip() or "the quote"
    quoted = float(quote.get("quoted_price") or quote.get("forecast_value") or 0)
    listed = float(quote.get("list_price") or 0)
    floor = float(quote.get("floor_price") or 0)
    discount = quote.get("discount_pct")
    if discount in (None, ""):
        discount = quote.get("discount_percentage")
    try:
        discount_pct = float(discount or 0)
    except (TypeError, ValueError):
        discount_pct = 0.0
    if listed and not discount_pct:
        discount_pct = round((1 - quoted / listed) * 100, 1)
    bundle_id = str(quote.get("bundle_id") or "").strip()
    from agents.data.revops import BUNDLES

    bundle = BUNDLES.get(bundle_id) or {}
    skus = [_pretty_sku(item) for item in (bundle.get("skus") or [])]
    lines = [
        _pretty_sku(str(row.get("sku_name") or ""))
        for row in (records.get("QuoteLine") or [])
        if isinstance(row, dict)
        and str(row.get("quote_id") or "") in {"", qid}
        and str(row.get("account") or "") in {"", who}
        and row.get("sku_name")
    ]
    scope = _join_scope(skus or lines) or str(bundle.get("name") or "the proposal")
    plant = ""
    blob = f"{bundle.get('name', '')} {' '.join(bundle.get('attach') or [])} {hint}".lower()
    if "dayton" in blob:
        plant = " for the Dayton plant"
    site_ask = ""
    errors = [str(item).lower() for item in (quote.get("quote_errors") or [])]
    codes = [str(item).upper() for item in (quote.get("validation_error_codes") or [])]
    if any("site" in item for item in errors) or "MISSING_SITE_CODE" in codes:
        site_ask = (
            " To keep licensing locked in, we still need the Dayton plant site "
            "code on the site license."
            if "dayton" in blob
            else " To keep licensing locked in, we still need the missing site code."
        )
    sandbox = str(opp.get("next_step") or "").strip()
    sandbox_line = (
        "In the meantime, I would like to get a sandbox date scheduled so you "
        "and the team can test the Dayton environment hands-on."
        if "sandbox" in sandbox.lower() or "dayton" in blob
        else "In the meantime, I would like to lock a short working session to close the remaining details."
    )
    subject = (
        f"{who} – Quote-to-Cash & Dayton Sandbox Next Steps"
        if "dayton" in blob and "quote-to-cash" in scope.lower()
        else f"{who} – Next Steps"
    )
    price_line = (
        f"We are currently targeting a total investment of {_money(quoted)}"
        + (
            f" (an {discount_pct:g}% discount off our {_money(listed)} list price)"
            if listed
            else ""
        )
        + "."
    )
    body = strip_email_signoff(
        f"Subject: {subject}\n\n"
        f"Hi {to},\n\n"
        "I hope you are having a great week.\n\n"
        f"I am following up on our proposal for the {who} {scope} deployment"
        f"{plant}.\n\n"
        f"{price_line}{site_ask}\n\n"
        f"{sandbox_line}\n\n"
        "Could you let me know your availability later this week or early next "
        "week for a brief call to align on the sandbox timeline and finalize "
        "the remaining details?\n\n"
        "Best regards,\n"
    )
    return CopyReadyArtifact(
        title=f"{qid} {who} — sendable email",
        kind="email",
        body=body,
    )


def _quote_mail_context(
    query: str,
    *,
    last_agent: str = "",
    last_topic: str = "",
) -> bool:
    if re.search(r"\b(quotes?|q-\d+|discount|floor|deal desk|gpo)\b", query, re.I):
        return True
    if str(last_agent or "") == "revops_quoting":
        return True
    return "quot" in str(last_topic or "").lower()


def _forecast_mail_context(
    query: str,
    *,
    last_agent: str = "",
    last_topic: str = "",
    last_territory: str = "",
    named_account: str = "",
) -> bool:
    if str(last_agent or "") in {"revops_forecast", "revops_reporting"}:
        return True
    if str(last_topic or "") in {
        "verbal",
        "rollup",
        "cover",
        "pacing",
        "match",
        "weekly",
        "backup",
        "crm_score",
    }:
        return True
    if last_territory and not named_account:
        return True
    return bool(re.search(r"verbal|rev intel|missing week|acv gap", query, re.I))


def _quote_status_mail_reply(
    results: dict[str, Any],
    query: str,
    last_account: str = "",
    *,
    last_agent: str = "",
    last_topic: str = "",
    last_territory: str = "",
) -> str:
    if not is_mail_follow_up(query):
        return ""
    if re.search(r"forecast value|missing a number", query, re.I):
        return ""
    named = detect_account_in_text(query) or ""
    if _forecast_mail_context(
        query,
        last_agent=last_agent,
        last_topic=last_topic,
        last_territory=last_territory,
        named_account=named,
    ) and not _quote_mail_context(query, last_agent=last_agent, last_topic=last_topic):
        return ""
    who = named or last_account
    quotes, records = _quote_rows_from_results(results)
    if not quotes and who:
        from agents.data.query import inspect_quoting

        pack = inspect_quoting(query, [who])
        records = pack.get("records") or {}
        quotes = [
            row for row in (records.get("Quote") or []) if isinstance(row, dict)
        ]
    if not quotes:
        return ""
    if not who:
        who = str(quotes[0].get("account") or "").strip()
    quote = next(
        (
            row
            for row in quotes
            if str(row.get("account") or "").strip() == who
        ),
        quotes[0],
    )
    who = str(quote.get("account") or who).strip() or who
    artifact = _quote_mail_artifact(who, quote, records)
    opp = _opportunity_for(who, records)
    qid = str(quote.get("quote_id") or "").strip() or "the quote"
    opp_id = str(quote.get("opp_id") or opp.get("opp_id") or "").strip()
    quoted = float(quote.get("quoted_price") or 0)
    listed = float(quote.get("list_price") or 0)
    floor = float(quote.get("floor_price") or 0)
    discount = quote.get("discount_pct", quote.get("discount_percentage") or 0)
    try:
        discount_pct = float(discount or 0)
    except (TypeError, ValueError):
        discount_pct = 0.0
    vs_floor = quoted - floor if floor else 0
    errors = [str(item) for item in (quote.get("quote_errors") or []) if item]
    codes = [str(item) for item in (quote.get("validation_error_codes") or [])]
    if "MISSING_SITE_CODE" in codes and not any("site" in item.lower() for item in errors):
        errors.append("Site license is missing the plant site code.")
    if quote.get("is_primary") is False or "NO_PRIMARY_AT_SS40" in codes:
        errors.append("The quote is not set as primary for stage progression.")
    stage = str(opp.get("stage_name") or quote.get("stage_name") or "").strip()
    complete = opp.get("stage_required_fields_complete_pct")
    health = opp.get("crm_health_score")
    notes = str(opp.get("manager_notes") or "").strip()
    next_step = str(opp.get("next_step") or "").strip()
    opp_bits = []
    if stage:
        opp_bits.append(f"stage {stage}")
    if complete not in (None, ""):
        opp_bits.append(f"{complete:g}% required fields completed")
    if health not in (None, ""):
        opp_bits.append(f"CRM health score {health}")
    overview = [
        f"Here is the status of quote {qid} for {who}"
        + (f" (Opportunity {opp_id})" if opp_id else "")
        + ", along with the issues blocking validation and a paste-ready email.",
        "",
        f"Quoted price: {_money(quoted)}"
        + (
            f" ({discount_pct:g}% discount off the {_money(listed)} list price)."
            if listed
            else "."
        ),
    ]
    if floor:
        side = "below" if vs_floor < 0 else "above"
        overview.append(
            f"Floor: quoted price is {_money(abs(vs_floor))} {side} floor "
            f"({_money(floor)} floor)."
        )
    from agents.data.revops import BUNDLES

    bundle = BUNDLES.get(str(quote.get("bundle_id") or ""), {})
    skus = [_pretty_sku(item) for item in (bundle.get("skus") or [])]
    if skus:
        plant = " for the Dayton plant" if "dayton" in str(bundle.get("name") or "").lower() else ""
        overview.append(f"Scope: {_join_scope(skus)}{plant}.")
    if errors:
        overview.append(
            "Validation: "
            + " ".join(
                item if item.endswith((".", "!", "?")) else f"{item}."
                for item in errors
            )
        )
    if opp_bits or notes or next_step:
        context = ", ".join(opp_bits)
        extra = " ".join(part.rstrip(".") for part in (notes, next_step) if part)
        overview.append(
            "Opportunity: "
            + ". ".join(part for part in (context, extra) if part)
            + "."
        )
    overview.append("")
    overview.append("```")
    overview.append(artifact.body.strip())
    overview.append("```")
    return "\n".join(overview).strip() + "\n"


def _verbal_call_mail_reply(
    results: dict[str, Any],
    query: str,
    *,
    last_account: str = "",
    last_territory: str = "",
    last_agent: str = "",
    last_topic: str = "",
) -> str:
    if not is_mail_follow_up(query):
        return ""
    named = detect_account_in_text(query) or ""
    if _quote_mail_context(query, last_agent=last_agent, last_topic=last_topic):
        return ""
    if not _forecast_mail_context(
        query,
        last_agent=last_agent,
        last_topic=last_topic,
        last_territory=last_territory,
        named_account=named,
    ):
        return ""
    from agents.data.query import inspect_forecast
    from agents.data.revops import resolve_scope

    geo = detect_territory_in_text(query) or ("" if named else last_territory)
    who = named or ("" if geo else last_account)
    accounts, _err = resolve_scope(geo=geo, account_name=who, query=query)
    if not accounts:
        return ""
    pack: dict[str, Any] = {}
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        if records.get("VerbalCallHistory") or payload.get("missing_data") is not None:
            pack = payload
            break
    if not pack:
        pack = inspect_forecast(query or "verbal call", accounts)
    records = pack.get("records") if isinstance(pack.get("records"), dict) else {}
    verbal_rows = [
        row
        for row in (records.get("VerbalCallHistory") or [])
        if isinstance(row, dict)
    ]
    if not verbal_rows:
        pack = inspect_forecast(query or "verbal call", accounts)
        records = pack.get("records") if isinstance(pack.get("records"), dict) else {}
        verbal_rows = [
            row
            for row in (records.get("VerbalCallHistory") or [])
            if isinstance(row, dict)
        ]
    boats = []
    for row in verbal_rows:
        name = str(row.get("rep_name") or "").strip()
        if name and name not in boats:
            boats.append(name)
    to = join_names(boats) or "team"
    week = next(
        (str(row.get("fiscal_week") or "").strip() for row in verbal_rows if row.get("fiscal_week")),
        "",
    )
    verbal_total = sum(int(row.get("verbal_call_acv") or 0) for row in verbal_rows)
    commit = int(pack.get("commit_total") or 0)
    coverage = pack.get("coverage")
    gaps = [str(item).strip() for item in (pack.get("missing_data") or []) if str(item).strip()]
    risks = [str(item).strip() for item in (pack.get("risks") or []) if str(item).strip()]
    place = who or (geo.title() if geo else "the book")
    subject = f"{place} verbal call" + (f" — {week}" if week else "")
    gap_lines = "\n".join(f"- {item}" for item in (gaps or risks)[:8]) or "- No missing week or ACV gap on the loaded rows."
    cover_bit = f"Coverage: {coverage}x.\n" if coverage not in (None, "") else ""
    body = strip_email_signoff(
        f"Subject: {subject}\n\n"
        f"Hi {to},\n\n"
        f"Here is the weekly verbal call for {place}.\n\n"
        + (f"Fiscal week: {week}.\n" if week else "")
        + f"Verbal call ACV: {_money(verbal_total)}.\n"
        + f"Commit ACV: {_money(commit)}.\n"
        + cover_bit
        + "\nACV gaps and missing weeks:\n"
        + f"{gap_lines}\n\n"
        "Please confirm the call number or flag any week that still needs a verbal "
        "before we lock the forecast.\n\n"
        "Best regards,\n"
    )
    overview = [
        f"Here is a paste-ready note on the {place} verbal call"
        + (f" for {week}" if week else "")
        + ", including ACV gaps and missing weeks.",
        "",
        "```",
        body.strip(),
        "```",
    ]
    return "\n".join(overview).strip() + "\n"


def _mail_follow_up_reply(
    results: dict[str, Any],
    query: str,
    *,
    last_account: str = "",
    last_territory: str = "",
    last_agent: str = "",
    last_topic: str = "",
) -> str:
    return _verbal_call_mail_reply(
        results,
        query,
        last_account=last_account,
        last_territory=last_territory,
        last_agent=last_agent,
        last_topic=last_topic,
    ) or _quote_status_mail_reply(
        results,
        query,
        last_account,
        last_agent=last_agent,
        last_topic=last_topic,
        last_territory=last_territory,
    )


def _remember_scope(state: Any, query: str, payload: Any) -> None:
    """Keep geo-scoped turns on the territory. Do not steal last_account from rows."""
    from agents.data.revops import keep_book_scope as _keep_book

    blob = f"{query} {json.dumps(payload, default=str)}" if payload is not None else query
    named_account = detect_account_in_text(query)
    named_geo = detect_territory_in_text(query)
    named_opp = detect_opportunity_in_text(query)
    if _keep_book(query, str(state.get("last_scope") or "")):
        state["last_scope"] = "book"
        apply_working_context(
            state,
            territory=named_geo or "",
            opportunity=named_opp or "",
        )
        return
    if named_account or named_opp:
        state["last_scope"] = "account"
        apply_working_context(
            state,
            account=named_account or "",
            territory=named_geo or "",
            opportunity=named_opp or "",
        )
        return
    if named_geo:
        state["last_scope"] = "territory"
        apply_working_context(state, territory=named_geo, opportunity=named_opp or "")
        return
    if str(state.get("last_territory") or "") and not named_account:
        apply_working_context(state, opportunity=named_opp or "")
        return
    if not str(state.get("last_account") or ""):
        apply_working_context(
            state,
            account=detect_account_in_text(blob) or "",
            territory=detect_territory_in_text(blob) or "",
            opportunity=named_opp or detect_opportunity_in_text(blob) or "",
        )
        return
    apply_working_context(state, territory=named_geo or "", opportunity=named_opp or "")


def _forecast_mail_artifact(
    who: str,
    quotes: list[dict[str, Any]],
    missing: list[str],
    records: dict[str, Any],
) -> CopyReadyArtifact:
    people = account_people(who)
    to_line = join_names(people) or _owner_for(who)
    geo = account_geo(who)
    opp = _opportunity_for(who, records)
    health = _health_for(who, records)
    email_log = _email_log_for(who, records)
    roles = _roles_for(who, records)
    lines: list[str] = []
    missing_ids: list[str] = []
    for row in quotes:
        qid = str(row.get("quote_id") or "").strip()
        amount = _quote_forecast_amount(row)
        stage = str(row.get("stage_name") or opp.get("stage_name") or "").strip()
        primary = bool(row.get("is_primary"))
        stage_bit = f" at {stage}" if stage else ""
        primary_bit = "primary " if primary else "non-primary "
        if amount <= 0:
            missing_ids.append(qid or "the quote")
            lines.append(
                f"{qid or 'The quote'} is the {primary_bit}quote{stage_bit} "
                "and still has no forecast value."
            )
        else:
            lines.append(
                f"{qid or 'The quote'} is the {primary_bit}quote{stage_bit} "
                f"with a forecast value of {_money(amount)}."
            )
    facts = "\n".join(f"- {line}" for line in lines) or f"- No quote rows for {who}."
    next_step = str(opp.get("next_step") or "").strip()
    manager_notes = str(opp.get("manager_notes") or "").strip()
    last_inbound = str(email_log.get("last_inbound_email_date") or "").strip()
    outbound = email_log.get("outbound_count_since_inbound")
    csm = str(health.get("csm_name") or "").strip()
    if missing:
        ask = (
            f"Please put a forecast value on "
            f"{', '.join(missing_ids) or who} so it can sit on the number. "
            + (f"The live next step is: {next_step} " if next_step else "")
        ).strip()
        title = f"{who} — missing forecast value"
    else:
        ask = (
            f"No missing number to chase on {who}. Confirm the forecast value "
            "stays on the call this week."
            + (f" Next step on the opp: {next_step}" if next_step else "")
        )
        title = f"{who} — forecast value on the quote"
    extra: list[str] = []
    if geo:
        extra.append(f"{who} sits in {geo}.")
    if roles:
        extra.append(f"Contact roles on the opp: {join_names(roles)}.")
    if csm:
        extra.append(f"{csm} is the CSM on the health row.")
    if last_inbound:
        extra.append(
            f"Last inbound mail was {last_inbound}"
            + (
                f", with {outbound} outbound since then."
                if outbound not in (None, "")
                else "."
            )
        )
    if manager_notes:
        extra.append(manager_notes.rstrip(".") + ".")
    extra_block = " ".join(extra)
    body = (
        f"Hi {to_line},\n\n"
        f"Sharing the forecast-value check on {who} from the current book "
        f"so everyone named on the account sees the same number.\n\n"
        f"{facts}\n\n"
        f"{extra_block}\n\n"
        f"{ask}\n\n"
        "Reply with the number you want on the quote, or flag if this should "
        "stay off the call.\n"
    )
    return CopyReadyArtifact(title=title, kind="email", body=body)


def _quote_label(row: dict[str, Any]) -> str:
    qid = str(row.get("quote_id") or "").strip()
    account = str(row.get("account") or "").strip()
    return f"{qid} {account}".strip()


def _book_forecast_value_briefing(
    quotes: list[dict[str, Any]], query: str
) -> SynthesisOutput:
    missing_rows = [
        row for row in quotes if _quote_forecast_amount(row) <= 0
    ]
    present_rows = [
        row for row in quotes if _quote_forecast_amount(row) > 0
    ]
    missing_labels = [_quote_label(row) for row in missing_rows]
    present_labels = [
        f"{_quote_label(row)} has a forecast value of "
        f"{_money(_quote_forecast_amount(row))}."
        for row in present_rows
    ]
    want_mail = is_mail_follow_up(query) if query else False
    insights = [
        f"{label} has no forecast value on the quote."
        for label in missing_labels
    ]
    insights.extend(present_labels)
    missing_phrase = join_names(missing_labels)
    if missing_rows:
        summary = (
            f"Across the loaded book, {len(missing_rows)} quote"
            f"{'s' if len(missing_rows) != 1 else ''} "
            f"{'have' if len(missing_rows) != 1 else 'has'} no forecast value: "
            f"{missing_phrase}. "
            + (
                f"The other {len(present_rows)} quote"
                f"{'s' if len(present_rows) != 1 else ''} already "
                f"{'have' if len(present_rows) != 1 else 'has'} a number."
                if present_rows
                else "No other loaded quote has a number yet."
            )
        )
        action = f"Put a forecast value on {missing_phrase}."
        paste = insights[0] if insights else ""
    elif present_rows:
        summary = (
            f"Every loaded quote on the book has a forecast number. "
            f"{present_labels[0]}"
        )
        action = "No missing forecast value to chase on the book."
        paste = present_labels[0]
    else:
        summary = "No quotes were loaded on the book."
        action = "Load quotes, then ask again."
        insights = [summary]
        paste = ""
    people: list[str] = []
    for row in missing_rows or present_rows:
        account = str(row.get("account") or "").strip()
        for name in account_people(account):
            if name not in people:
                people.append(name)
    people_phrase = join_names(people)
    artifacts: list[CopyReadyArtifact] = []
    if want_mail:
        targets = missing_rows or present_rows
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in targets:
            account = str(row.get("account") or "").strip()
            if not account:
                continue
            grouped.setdefault(account, []).append(row)
        if not grouped:
            grouped = {"the book": quotes}
        draft_lines: list[str] = []
        for account, rows in grouped.items():
            account_quotes = [
                quote
                for quote in quotes
                if str(quote.get("account") or "").strip() == account
            ] or rows
            missing_facts = [
                f"{_quote_label(row)} has no forecast value on the quote."
                for row in account_quotes
                if _quote_forecast_amount(row) <= 0
            ]
            qid = str((account_quotes or rows)[0].get("quote_id") or "").strip()
            to = join_names(account_people(account)) or _owner_for(account)
            draft_lines.append(
                f"{qid} {account} goes to {to}."
            )
            artifacts.append(
                _forecast_mail_artifact(
                    account,
                    account_quotes,
                    missing_facts,
                    {},
                )
            )
        who_to = people_phrase or "the owners on these quotes"
        noun = "note" if len(artifacts) == 1 else "notes"
        summary = (
            f"{len(artifacts)} paste-ready {noun} below — "
            f"{' '.join(draft_lines)}"
        )
        action = (
            f"Send the draft to {who_to}."
            if len(artifacts) == 1
            else f"Send the drafts to {who_to}."
        )
        insights = draft_lines
        paste = draft_lines[0] if draft_lines else ""
    return SynthesisOutput(
        summary=" ".join(summary.split()).strip(),
        insights=insights[:8],
        actions=[
            RecommendedAction(
                action=action,
                owner=people[0] if people else "you",
                due="now",
                paste=paste,
            )
        ],
        artifacts=artifacts,
    )


def _forecast_value_briefing(
    quotes: list[dict[str, Any]],
    who: str,
    query: str,
    records: dict[str, Any] | None = None,
) -> SynthesisOutput:
    from agents.data.revops import is_book_wide

    records = records or {}
    accounts = [
        str(row.get("account") or "").strip()
        for row in quotes
        if str(row.get("account") or "").strip()
    ]
    unique_accounts = list(dict.fromkeys(accounts))
    if is_book_wide(query) or len(unique_accounts) > 1:
        return _book_forecast_value_briefing(quotes, query)
    opp = _opportunity_for(who, records)
    health = _health_for(who, records)
    email_log = _email_log_for(who, records)
    people = account_people(who)
    people_phrase = join_names(people)
    roles = _roles_for(who, records)
    stage = str(opp.get("stage_name") or "").strip()
    next_step = str(opp.get("next_step") or "").strip()
    manager_notes = str(opp.get("manager_notes") or "").strip()
    missing_facts: list[str] = []
    present_facts: list[str] = []
    missing_ids: list[str] = []
    for row in quotes:
        qid = str(row.get("quote_id") or "")
        account = str(row.get("account") or who)
        amount = _quote_forecast_amount(row)
        label = f"{qid} {account}".strip()
        row_stage = str(row.get("stage_name") or stage)
        if amount <= 0:
            missing_ids.append(qid or label)
            missing_facts.append(f"{label} has no forecast value on the quote.")
        else:
            present_facts.append(
                f"{label} has a forecast value of {_money(amount)}"
                + (f" at {row_stage}." if row_stage else ".")
            )
    follow = is_finding_follow_up(query) if query else False
    want_mail = is_mail_follow_up(query) if query else False
    want_next = is_action_follow_up(query) if query else False
    insights: list[str] = []
    insights.extend(missing_facts)
    insights.extend(present_facts[:4])
    if stage:
        pct = opp.get("stage_required_fields_complete_pct")
        try:
            complete = f" and required fields are {float(pct):g}% complete"
        except (TypeError, ValueError):
            complete = ""
        insights.append(
            f"{who} is at {stage}{complete}."
        )
    if next_step:
        insights.append(f"Live next step: {next_step}")
    if manager_notes:
        insights.append(manager_notes)
    if people_phrase:
        insights.append(f"People on the account: {people_phrase}.")
    if roles:
        insights.append(f"Contact roles logged: {join_names(roles)}.")
    last_inbound = str(email_log.get("last_inbound_email_date") or "").strip()
    if last_inbound:
        insights.append(f"Last inbound email was {last_inbound}.")

    if missing_facts:
        qid = missing_ids[0] if missing_ids else "the quote"
        if want_next:
            summary = (
                f"On {who}, "
                + (
                    f"start with {next_step.rstrip('.')}. "
                    if next_step
                    else ""
                )
                + f"Also put a forecast value on {qid} — {missing_facts[0]} "
                + (
                    f"Manager note: {manager_notes.rstrip('.')}. "
                    if manager_notes
                    else ""
                )
                + (
                    f"Work this with {people_phrase}."
                    if people_phrase
                    else ""
                )
            )
        elif follow:
            summary = (
                f"Yes — this is material on {who}. {missing_facts[0]} "
                + (f"The opp is at {stage}. " if stage else "")
                + (
                    f"Manager note says {manager_notes.rstrip('.')}. "
                    if manager_notes
                    else ""
                )
                + (
                    f"Until a number is on {qid}, it should not sit in the call."
                )
            )
        else:
            summary = (
                f"{who} still has {len(missing_facts)} quote"
                f"{'s' if len(missing_facts) != 1 else ''} with no forecast "
                f"number. {missing_facts[0]} "
                + (f"That quote is at {stage}. " if stage else "")
                + (
                    f"The people to loop in are {people_phrase}. "
                    if people_phrase
                    else ""
                )
                + (
                    f"The live next step is {next_step.rstrip('.')}. "
                    if next_step
                    else ""
                )
            )
        action = (
            next_step.rstrip(".") + f", and put a forecast value on {qid}."
            if next_step
            else f"Put a forecast value on {qid}."
        )
        paste = missing_facts[0]
    elif present_facts:
        if want_next:
            summary = (
                f"On {who}, forecast value is already on the quote — "
                f"{present_facts[0]} "
                + (
                    f"Your next step is {next_step.rstrip('.')}. "
                    if next_step
                    else "There is no missing number to chase. "
                )
                + (
                    f"{manager_notes.rstrip('.')}. "
                    if manager_notes
                    else ""
                )
                + (
                    f"Keep {people_phrase} in the loop."
                    if people_phrase
                    else ""
                )
            )
        elif follow:
            summary = (
                f"No — this is not a crucial gap on {who}. {present_facts[0]} "
                + (
                    f"Keep {people_phrase} aligned that the number stays on the call."
                    if people_phrase
                    else "The number is already on the quote."
                )
            )
        else:
            summary = (
                f"{who}: every loaded quote has a forecast number. "
                f"{present_facts[0]} "
                + (
                    f"{people_phrase} already have a number they can stand behind. "
                    if people_phrase
                    else ""
                )
                + (f"Next step on the opp: {next_step}" if next_step else "")
            )
        action = (
            next_step
            if want_next and next_step
            else f"No missing forecast value to chase on {who}."
        )
        paste = next_step if want_next and next_step else present_facts[0]
    else:
        summary = f"No quotes matched {who}."
        action = "Name a loaded account with quotes."
        insights = [summary]
        paste = ""
    if want_mail:
        who_to = people_phrase or _owner_for(who)
        qid = missing_ids[0] if missing_ids else (
            str(quotes[0].get("quote_id") or "").strip() if quotes else who
        )
        summary = (
            f"Paste-ready note below for {qid} {who} to {who_to}. "
            + (
                missing_facts[0]
                if missing_facts
                else present_facts[0] if present_facts else ""
            )
        )
        action = f"Send the draft to {who_to}."
        insights = [
            f"Note for {qid} {who} goes to {who_to}.",
            *(missing_facts[:2] or present_facts[:2]),
        ]
        paste = missing_facts[0] if missing_facts else (
            present_facts[0] if present_facts else ""
        )
    artifacts = (
        [_forecast_mail_artifact(who, quotes, missing_facts, records)]
        if want_mail
        else []
    )
    steps = [
        RecommendedAction(
            action=action,
            owner=people[0] if people else "you",
            due="now",
            paste=paste,
        )
    ]
    if want_next and missing_ids and next_step and next_step.rstrip(".") not in action:
        steps.append(
            RecommendedAction(
                action=f"Put a forecast value on {missing_ids[0]}.",
                owner=people[0] if people else "you",
                due="now",
                paste=missing_facts[0] if missing_facts else "",
            )
        )
    return SynthesisOutput(
        summary=" ".join(summary.split()).strip(),
        insights=insights[:8],
        actions=steps,
        artifacts=artifacts,
    )


def _records_fallback(
    payload: dict[str, Any],
    records: dict[str, Any],
    query: str = "",
) -> SynthesisOutput | None:
    """Turn hygiene / quoting / OTC rows into a briefing when KPI slides are absent."""
    name = _named_account(payload, records)
    topic = str(payload.get("topic") or "")
    gaps = [str(item).strip() for item in (payload.get("gaps") or []) if str(item).strip()]
    lines = [str(item).strip() for item in (payload.get("lines") or []) if str(item).strip()]
    holds = [str(item).strip() for item in (payload.get("holds") or []) if str(item).strip()]
    errors = [str(item).strip() for item in (payload.get("errors") or []) if str(item).strip()]
    deviations = [
        str(item).strip()
        for item in (payload.get("deviations") or [])
        if str(item).strip()
    ]
    quotes = [row for row in (records.get("Quote") or []) if isinstance(row, dict)]
    opps = records.get("Opportunity") or []
    if quotes or topic == "forecast_value":
        who = name or "This account"
        if (
            topic == "forecast_value"
            or is_mail_follow_up(query)
            or re.search(r"forecast value|missing a number", query, re.I)
        ):
            return _forecast_value_briefing(quotes, who, query, records)
        if errors or deviations:
            insights = (errors + deviations)[:8]
            artifacts: list[CopyReadyArtifact] = []
            if is_mail_follow_up(query) and quotes:
                artifacts.append(
                    _quote_mail_artifact(who, quotes[0], records)
                )
            return SynthesisOutput(
                summary=f"{who} quoting needs a look. {insights[0]}",
                insights=insights,
                actions=[
                    RecommendedAction(
                        action=f"Fix the quote gaps on {who}.",
                        owner="you",
                        due="now",
                        paste=insights[0],
                    )
                ],
                artifacts=artifacts,
            )
    if gaps or opps:
        insights: list[str] = []
        for row in opps[:6]:
            if not isinstance(row, dict):
                continue
            pct = row.get("stage_required_fields_complete_pct")
            try:
                complete = float(pct)
            except (TypeError, ValueError):
                complete = 100.0
            if complete >= 90:
                continue
            insights.append(
                f"{row.get('account')} {row.get('opp_id')} at "
                f"{row.get('stage_name')} is only {pct}% complete "
                "on required fields."
            )
        if not insights:
            insights = [
                item.replace(
                    "stage_required_fields_complete_pct=",
                    "required fields ",
                )
                for item in gaps[:6]
            ]
        if not insights:
            return None
        who = name or "This account"
        return SynthesisOutput(
            summary=(
                f"{who} has incomplete stage hygiene. "
                f"{insights[0]}"
            ),
            insights=insights[:8],
            actions=[
                RecommendedAction(
                    action=f"Close the open required fields on {who}.",
                    owner="you",
                    due="now",
                    paste=insights[0],
                )
            ],
        )
    if holds or lines:
        insights = (holds + lines)[:8]
        who = name or "This account"
        return SynthesisOutput(
            summary=f"{who} order-to-cash: {insights[0]}",
            insights=insights,
            actions=[
                RecommendedAction(
                    action=f"Clear the {who} hold or confirm ARR before booking.",
                    owner="you",
                    due="now",
                    paste=insights[0],
                )
            ],
        )
    if errors or deviations:
        insights = (errors + deviations)[:8]
        who = name or "This account"
        return SynthesisOutput(
            summary=f"{who} quoting needs a look. {insights[0]}",
            insights=insights,
            actions=[
                RecommendedAction(
                    action=f"Fix the quote gaps on {who}.",
                    owner="you",
                    due="now",
                    paste=insights[0],
                )
            ],
        )
    return None


def _account_from_results(results: dict[str, Any]) -> str:
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        name = _named_account(payload, payload.get("records") or {})
        if name:
            return name
    return ""


def _record_fact_tokens(results: dict[str, Any]) -> list[str]:
    """Quote/opp ids and money figures the briefing must actually use."""
    tokens: list[str] = []
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        rows: list[Any] = []
        for value in records.values():
            if isinstance(value, list):
                rows.extend(value)
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("quote_id", "opp_id"):
                item = str(row.get(key) or "").strip()
                if item:
                    tokens.append(item.lower())
            for key in (
                "forecast_value",
                "quoted_price",
                "verbal_call_acv",
                "pipeline_coverage_ratio",
            ):
                raw = row.get(key)
                if raw in (None, ""):
                    continue
                try:
                    number = float(raw)
                except (TypeError, ValueError):
                    continue
                tokens.append(str(int(number)) if number == int(number) else str(number))
                if abs(number) >= 1000:
                    tokens.append(f"{int(number):,}")
    return tokens


def _cites_record_facts(
    output: SynthesisOutput, results: dict[str, Any]
) -> bool:
    tokens = _record_fact_tokens(results)
    if not tokens:
        return True
    blob = " ".join(
        [
            output.summary,
            *output.insights,
            *(action.action for action in output.actions),
            *(action.paste for action in output.actions),
        ]
    ).lower()
    return any(token.lower() in blob for token in tokens)


def _usable_synthesis(
    output: SynthesisOutput | None, results: dict[str, Any]
) -> bool:
    if output is None:
        return False
    if validate_synthesis_output(output, forbidden_terms=_INTERNAL_TERMS):
        return False
    return _cites_record_facts(output, results)


def _empty_synthesis(account: str = "") -> SynthesisOutput:
    briefing = empty_book_briefing(account)
    return SynthesisOutput(
        summary=str(briefing["summary"]),
        insights=[str(item) for item in briefing["insights"]],
        actions=[
            RecommendedAction(
                action=str(briefing["action"]),
                owner="you",
                due="now",
                paste="",
            )
        ],
    )


def _grounded_fallback(
    results: dict[str, Any], query: str = ""
) -> SynthesisOutput | None:
    """Build a briefing from specialist rows when synthesis stays hollow."""
    for payload in results.values():
        if not isinstance(payload, dict):
            continue
        records = payload.get("records") or {}
        periods = records.get("KpiPeriod") or []
        kpis = records.get("KpiSummary") or {}
        slides = [
            str(item).strip()
            for item in (payload.get("slides") or [])
            if str(item).strip()
        ]
        copy_ready = [
            str(item).strip()
            for item in (payload.get("copy_ready") or [])
            if str(item).strip()
        ]
        if not periods and not slides and not kpis and not copy_ready:
            briefing = _records_fallback(payload, records, query)
            if briefing:
                return briefing
            continue
        insights: list[str] = []
        for row in periods:
            insights.append(
                f"{str(row.get('period', '')).title()}: coverage "
                f"{row.get('pipeline_coverage_ratio')}x, verbal call "
                f"${int(row.get('verbal_call_acv') or 0):,}, landing "
                f"${int(row.get('landing_projected') or 0):,}, cycle "
                f"{row.get('avg_sales_cycle_days')} days."
            )
        if not insights:
            insights = slides[1:] or slides[:3] or copy_ready[:3]
        if not insights and kpis:
            insights = [
                (
                    f"Coverage {kpis.get('pipeline_coverage_ratio')}x, "
                    f"verbal call ${int(kpis.get('verbal_call_acv') or 0):,}, "
                    f"quarterly landing "
                    f"${int(kpis.get('quarterly_landing_projected') or 0):,}, "
                    f"cycle {kpis.get('avg_sales_cycle_days')} days."
                )
            ]
        headline = (
            slides[0]
            if slides
            else copy_ready[0]
            if copy_ready
            else "Here are the numbers from the current book."
        )
        if copy_ready and headline == copy_ready[0]:
            summary = copy_ready[0]
        elif copy_ready:
            summary = f"{headline} {copy_ready[0]}"
        elif kpis:
            summary = (
                f"{headline} Coverage is {kpis.get('pipeline_coverage_ratio')}x, "
                f"verbal call ${int(kpis.get('verbal_call_acv') or 0):,}, "
                f"quarterly landing "
                f"${int(kpis.get('quarterly_landing_projected') or 0):,}, "
                f"cycle {kpis.get('avg_sales_cycle_days')} days."
            )
        else:
            summary = headline
        artifacts: list[CopyReadyArtifact] = []
        body = "\n".join(slides or copy_ready)
        if body:
            artifacts.append(
                CopyReadyArtifact(
                    title="Snapshot",
                    kind="talking_points",
                    body=body,
                )
            )
        return SynthesisOutput(
            summary=summary.strip(),
            insights=insights[:8],
            actions=[
                RecommendedAction(
                    action="Use these numbers on the next forecast or QBR conversation.",
                    owner="Account Executive",
                    due="Today",
                    paste=copy_ready[0] if copy_ready else "",
                )
            ],
            artifacts=artifacts,
        )
    return None


class SellerCopilotWorkflow(BaseAgent):
    """Run a validated route instead of asking an LLM to choreograph tools."""

    planner_agent: Agent
    specialist_agents: dict[str, Agent] = {}
    final_synthesis_agent: Agent
    domain_agents: dict[str, Agent] = {}

    def model_post_init(self, __context: Any) -> None:
        domains = dict(self.domain_agents)
        specialists = dict(self.specialist_agents)
        for child in self.sub_agents:
            if child.name.endswith("_orchestrator"):
                domains[child.name] = child
                for spec in child.sub_agents or []:
                    specialists[spec.name] = spec
        object.__setattr__(self, "domain_agents", domains)
        object.__setattr__(self, "specialist_agents", specialists)

    def _child_ctx(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
    ) -> InvocationContext:
        return ctx.model_copy(update={"user_content": _content(request)})

    async def _run_child(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
    ) -> tuple[list[Event], Any, str]:
        child_ctx = self._child_ctx(agent, ctx, request)
        if agent.name in REVOPS_AGENT_IDS:
            try:
                payload = execute_revops(agent.name, request)
            except Exception as exc:  # keep one failed specialist from killing the turn
                return [], None, f"{type(exc).__name__}: {exc}"
            return (
                [
                    Event(
                        invocation_id=ctx.invocation_id,
                        author=agent.name,
                        branch=child_ctx.branch,
                    )
                ],
                payload,
                "",
            )
        events: list[Event] = []
        error = ""
        try:
            async with asyncio.timeout(CHILD_TIMEOUT_SECONDS):
                async for event in agent.run_async(child_ctx):
                    events.append(event)
        except TimeoutError:
            error = f"Timeout after {CHILD_TIMEOUT_SECONDS}s"
        except Exception as exc:  # keep one failed specialist from killing the turn
            error = f"{type(exc).__name__}: {exc}"
        return events, _parse_payload(events), error

    async def _stream_child(
        self,
        agent: BaseAgent,
        ctx: InvocationContext,
        request: str,
        result: list[Any],
        *,
        text_only: bool = False,
    ) -> AsyncGenerator[Event, None]:
        """Yield child events as they arrive; append [payload, error] to result."""
        if not hasattr(agent, "run_async"):
            events, payload, error = await self._run_child(agent, ctx, request)
            if text_only:
                payload = _joined_event_text(events) or (
                    payload if isinstance(payload, str) else ""
                )
            result.extend([payload, error])
            for event in events:
                yield event
            return
        events: list[Event] = []
        error = ""
        try:
            async with asyncio.timeout(CHILD_TIMEOUT_SECONDS):
                async for event in agent.run_async(self._child_ctx(agent, ctx, request)):
                    events.append(event)
                    yield event
        except TimeoutError:
            error = f"Timeout after {CHILD_TIMEOUT_SECONDS}s"
        except Exception as exc:  # keep one failed specialist from killing the turn
            error = f"{type(exc).__name__}: {exc}"
        payload: Any = (
            _joined_event_text(events) if text_only else _parse_payload(events)
        )
        result.extend([payload, error])

    def _planner_request(self, query: str) -> str:
        return query

    def _specialist_request(self, query: str, state: Any) -> str:
        from agents.data.revops import keep_book_scope, parse_scope_from_text

        context = {key: str(state.get(key) or "") for key in SESSION_KEYS}
        scope = parse_scope_from_text(query)
        last_scope = str(context.get("last_scope") or "")
        if keep_book_scope(query, last_scope):
            scope["account_name"] = ""
            scope["geo"] = ""
            scope["boat"] = ""
            scope["opp_id"] = ""
        elif not scope.get("account_name") and last_scope in {"territory", "book"} and context.get("last_territory"):
            if not scope.get("geo"):
                scope["geo"] = context["last_territory"]
        elif not scope.get("account_name") and context.get("last_account"):
            scope["account_name"] = context["last_account"]
        elif not any(scope.values()) and context.get("last_territory"):
            scope["geo"] = context["last_territory"]
        return (
            f"Original request: {query}\n"
            "Tool scope — pass these arguments exactly. west/central/south/east "
            "are geos, never account_name:\n"
            f"{json.dumps(scope, ensure_ascii=False)}\n"
            "Working context:\n"
            f"{json.dumps(context, ensure_ascii=False)}\n"
            "Use the named account, territory, or opportunity from the request "
            "or earlier turns in this session. Return the structured result and "
            "a markdown reply in the shape that fits the ask."
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        query = _user_text(ctx).strip().strip("'\"")
        state = ctx.session.state
        for key in SESSION_KEYS:
            state.setdefault(key, "")
        seed_context_from_text(state, query)

        planner_events, raw_plan, _planner_error = await self._run_child(
            self.planner_agent,
            ctx,
            self._planner_request(query),
        )
        for event in planner_events:
            yield event
        planned = DomainDecision.from_state(
            raw_plan or state.get("domain_decision")
        )
        write_debug_log(
            "planner",
            {
                "query": query,
                "event_count": len(planner_events),
                "domain_id": planned.domain_id,
                "direct_reply": planned.direct_reply,
                "clarifying_question": planned.clarifying_question,
                "planner_error": _planner_error,
            },
        )
        domain_id = planned.domain_id
        if domain_id not in (self.domain_agents or {}) and domain_id not in {
            "forecast_orchestrator",
            "quoting_orchestrator",
            "reporting_orchestrator",
            "hygiene_orchestrator",
            "otc_orchestrator",
            "pricing_orchestrator",
        }:
            domain_id = ""

        if not domain_id:
            reply = planned.direct_reply or planned.clarifying_question
            if reply:
                yield _final_event(self.name, ctx, reply)
            return

        selected = specialists_in_domain(domain_id)
        selected = [
            name for name in selected if name in self.specialist_agents
        ]
        selected = list(dict.fromkeys(selected))
        if not selected:
            reply = planned.clarifying_question or planned.direct_reply
            if reply:
                yield _final_event(self.name, ctx, reply)
            return
        request = self._specialist_request(query, state)
        results: dict[str, Any] = {}

        async def _run_named(name: str) -> tuple[str, list[Event], Any, str]:
            events, payload, error = await self._run_child(
                self.specialist_agents[name], ctx, request
            )
            return name, events, payload, error

        pending = [asyncio.create_task(_run_named(name)) for name in selected]
        for finished in asyncio.as_completed(pending):
            name, events, payload, error = await finished
            for event in events:
                yield event
            if error:
                results[name] = {"status": "error", "error": error}
            elif payload is None:
                results[name] = {
                    "status": "error",
                    "error": "Specialist returned no structured payload.",
                }
            else:
                results[name] = payload
            state["last_agent"] = name
            topic = ""
            if isinstance(results.get(name), dict):
                topic = str(results[name].get("topic") or "")
            if topic:
                state["last_topic"] = topic
            _remember_scope(state, query, results[name])

        mail_reply = _mail_follow_up_reply(
            results,
            query,
            last_account=str(state.get("last_account") or ""),
            last_territory=str(state.get("last_territory") or ""),
            last_agent=str(state.get("last_agent") or ""),
            last_topic=str(state.get("last_topic") or ""),
        )
        if mail_reply:
            write_debug_log(
                "quote_mail",
                {
                    "query": query,
                    "specialists": list(results.keys()),
                    "record_counts": _record_counts(results),
                },
            )
            yield _final_event(self.name, ctx, mail_reply)
            return

        replies = _specialist_replies(results)
        if replies:
            write_debug_log(
                "specialist_reply",
                {
                    "query": query,
                    "specialists": list(results.keys()),
                    "record_counts": _record_counts(results),
                },
            )
            yield _final_event(self.name, ctx, "\n\n".join(replies))
            return

        synthesis_request = build_synthesis_request(
            user_query=query,
            state=state,
            results=results,
        )
        # ADK builds model contents from session events, not user_content.
        # Park the rows as the current user turn, then remove them so they
        # do not leak into the next planner call.
        injected = Event(
            invocation_id=ctx.invocation_id,
            author="user",
            branch=ctx.branch,
            content=_content(synthesis_request),
        )
        ctx.session.events.append(injected)
        yield Event(
            invocation_id=ctx.invocation_id,
            author="synthesis",
            branch=ctx.branch,
        )
        synthesis_result: list[Any] = []
        try:
            async for event in self._stream_child(
                self.final_synthesis_agent,
                ctx,
                synthesis_request,
                synthesis_result,
                text_only=True,
            ):
                yield event
        finally:
            try:
                ctx.session.events.remove(injected)
            except ValueError:
                pass
        raw_synthesis, synthesis_error = (
            synthesis_result
            if len(synthesis_result) == 2
            else (None, "Synthesis returned no result.")
        )
        text = raw_synthesis.strip() if isinstance(raw_synthesis, str) else ""
        write_debug_log(
            "synthesis",
            {
                "query": query,
                "specialists": list(results.keys()),
                "record_counts": _record_counts(results),
                "request_chars": len(synthesis_request),
                "synthesis_error": synthesis_error,
                "reply_chars": len(text),
            },
        )
        if not text:
            text = "I couldn't finish that answer. Try again."
        mail_reply = _mail_follow_up_reply(
            results,
            query,
            last_account=str(state.get("last_account") or ""),
            last_territory=str(state.get("last_territory") or ""),
            last_agent=str(state.get("last_agent") or ""),
            last_topic=str(state.get("last_topic") or ""),
        )
        if mail_reply:
            text = mail_reply

        yield _final_event(self.name, ctx, text)
