"""Query dummy RevOps tables and return records for synthesis to write from."""

from __future__ import annotations

import json
from typing import Any

from agents.data.revops import coerce_scope, keep_book_scope, resolve_scope
from agents.data.query import (
    inspect_forecast,
    inspect_hygiene,
    inspect_otc,
    inspect_pricing,
    inspect_quoting,
    inspect_reporting,
)
from models.specialist_outputs import (
    RevopsForecastOutput,
    RevopsHygieneOutput,
    RevopsOtcOutput,
    RevopsPricingOutput,
    RevopsQuotingOutput,
    RevopsReportingOutput,
)

REVOPS_AGENT_IDS = (
    "revops_forecast",
    "revops_quoting",
    "revops_reporting",
    "revops_hygiene",
    "revops_otc",
    "revops_pricing",
)


def _user_query(request: str) -> str:
    """Keep geo words in the tool-scope blurb from stealing the filter."""
    for line in request.splitlines():
        if line.startswith("Original request:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return request


def _json_after(label: str, request: str) -> dict[str, Any]:
    idx = request.find(label)
    if idx < 0:
        return {}
    start = request.find("{", idx)
    if start < 0:
        return {}
    try:
        parsed, _end = json.JSONDecoder().raw_decode(request[start:])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _accounts(request: str) -> tuple[list[str], dict[str, str], str]:
    query = _user_query(request)
    tool_scope = _json_after("Tool scope", request)
    context = _json_after("Working context", request)
    scope = coerce_scope(
        geo=str(tool_scope.get("geo") or ""),
        boat=str(tool_scope.get("boat") or ""),
        account_name=str(tool_scope.get("account_name") or ""),
        opp_id=str(tool_scope.get("opp_id") or ""),
        query=query,
    )
    if keep_book_scope(query, str(context.get("last_scope") or "")):
        scope["account_name"] = ""
        scope["geo"] = ""
        scope["boat"] = ""
        scope["opp_id"] = ""
    elif not scope["account_name"]:
        scope["account_name"] = str(context.get("last_account") or "")
        if not scope["account_name"] and not scope["geo"]:
            scope["geo"] = str(context.get("last_territory") or "")
    accounts, err = resolve_scope(query=query, **scope)
    message = ""
    if err:
        message = str(err.get("message") or "Scope could not be resolved.")
        accounts = []
    return accounts, scope, message


def execute_revops(agent_id: str, request: str) -> dict[str, Any]:
    """Return a filled specialist payload for a task-menu RevOps ask."""
    if agent_id == "revops_forecast":
        return _forecast(request)
    if agent_id == "revops_quoting":
        return _quoting(request)
    if agent_id == "revops_reporting":
        return _reporting(request)
    if agent_id == "revops_hygiene":
        return _hygiene(request)
    if agent_id == "revops_otc":
        return _otc(request)
    if agent_id == "revops_pricing":
        return _pricing(request)
    raise KeyError(agent_id)


def _attach(payload: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    payload["owner"] = pack.get("owner") or ""
    payload["artifact_title"] = pack.get("artifact_title") or ""
    payload["artifact_body"] = pack.get("artifact_body") or ""
    return payload


def _forecast(request: str) -> dict[str, Any]:
    accounts, scope, error = _accounts(request)
    pack = inspect_forecast(_user_query(request), accounts)
    return _attach(
        RevopsForecastOutput(
            geo=scope["geo"],
            boat=scope["boat"] or pack.get("owner") or "",
            commit_total=pack["commit_total"],
            upside_total=pack["upside_total"],
            coverage=pack["coverage"],
            missing_data=pack["missing_data"],
            risks=pack["risks"],
            accounts=pack["accounts"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if error else "success",
            error=error,
        ).model_dump(),
        pack,
    )


def _quoting(request: str) -> dict[str, Any]:
    accounts, _scope_data, error = _accounts(request)
    context = _json_after("Working context", request)
    query = _user_query(request)
    pack = inspect_quoting(query, accounts)
    if not pack["topic"]:
        pack["topic"] = str(context.get("last_topic") or "deviation")
    return _attach(
        RevopsQuotingOutput(
            quotes=pack["quotes"],
            deviations=pack["deviations"],
            errors=pack["errors"],
            bundles=pack["bundles"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if error else "success",
            error=error,
        ).model_dump(),
        pack,
    )


def _reporting(request: str) -> dict[str, Any]:
    accounts, _scope_data, error = _accounts(request)
    pack = inspect_reporting(_user_query(request), accounts)
    return _attach(
        RevopsReportingOutput(
            report_type=pack["report_type"],
            slides=pack["slides"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if error else "success",
            error=error,
        ).model_dump(),
        pack,
    )


def _hygiene(request: str) -> dict[str, Any]:
    accounts, _scope_data, error = _accounts(request)
    pack = inspect_hygiene(_user_query(request), accounts)
    return _attach(
        RevopsHygieneOutput(
            accounts=pack["accounts"],
            gaps=pack["gaps"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if error else "success",
            error=error,
        ).model_dump(),
        pack,
    )


def _otc(request: str) -> dict[str, Any]:
    accounts, _scope_data, error = _accounts(request)
    pack = inspect_otc(_user_query(request), accounts)
    return _attach(
        RevopsOtcOutput(
            accounts=pack["accounts"],
            arr_total=pack["arr_total"],
            headroom_total=pack["headroom_total"],
            holds=pack["holds"],
            lines=pack["lines"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if error else "success",
            error=error,
        ).model_dump(),
        pack,
    )


def _pricing(request: str) -> dict[str, Any]:
    accounts, _scope_data, error = _accounts(request)
    pack = inspect_pricing(_user_query(request), accounts)
    missing = "" if pack["account"] else (
        error or "Pricing analytics needs an account, opp, geo, or boat."
    )
    return _attach(
        RevopsPricingOutput(
            account=pack["account"],
            sku=pack["sku"],
            waterfall=pack["waterfall"],
            below_floor=pack["below_floor"],
            peer_band=pack["peer_band"],
            findings=pack["findings"],
            records=pack.get("records") or {},
            topic=pack["topic"],
            next_action=pack["next_action"],
            copy_ready=pack["copy_ready"],
            status="error" if (error or missing) else "success",
            error=error or missing,
        ).model_dump(),
        pack,
    )
