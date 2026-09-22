"""Mock RevOps book: forecast rollups, quotes, bundles, credit/ARR, pricing."""

from __future__ import annotations

import re
from typing import Any

from agents.data.crm import ACCOUNTS, OPPORTUNITIES, TERRITORIES, resolve_account
from agents.data.dummy_store import (
    load_bundles,
    load_credit_arr,
    load_forecast_gaps,
    load_forecast_meta,
    load_opportunities,
    load_quote_pricing,
)
from agents.data.pillar import DEAL_RISKS, PRICING
from agents.tooling import error

FORECAST_GAPS = load_forecast_gaps()
FORECAST_META = load_forecast_meta()
QUOTES = load_quote_pricing()
BUNDLES = load_bundles()
CREDIT_ARR = load_credit_arr()

_GEOS = ("west", "central", "south", "east")
_OPP_RE = re.compile(r"\bOPP-\d+\b", re.IGNORECASE)
_BOOK_WIDE_RE = re.compile(
    r"\b("
    r"all quotes?|every quote|all accounts?|every account|"
    r"the (?:whole |full |entire )?book|across (?:the )?book|"
    r"book.?wide|all deals?"
    r")\b"
)


def _owners() -> list[str]:
    return sorted(
        {str(record["owner"]) for record in ACCOUNTS.values() if record.get("owner")},
        key=len,
        reverse=True,
    )


def _account_in_text(text: str) -> str:
    lowered = text.lower()
    ranked = sorted(ACCOUNTS, key=len, reverse=True)
    for name in ranked:
        if name.lower() in lowered:
            return name
        record = ACCOUNTS[name]
        for alias in [record.get("legal_name", ""), *record.get("aliases", [])]:
            if alias and str(alias).lower() in lowered:
                return name
    return ""


def _geo_alias(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in _GEOS:
        return lowered
    for geo in _GEOS:
        if re.search(rf"\b{geo}\b", lowered):
            return geo
    return ""


def is_book_wide(query: str) -> bool:
    """True when the AE asked for the whole book, not last_account or one geo."""
    lowered = query.lower()
    if any(re.search(rf"\b{geo}\b", lowered) for geo in _GEOS):
        return False
    if _account_in_text(query) or _OPP_RE.search(query):
        return False
    return bool(_BOOK_WIDE_RE.search(lowered))


def keep_book_scope(query: str, last_scope: str = "") -> bool:
    """Stay on the full book for follow-ups like 'create email artifacts'."""
    if is_book_wide(query):
        return True
    if str(last_scope or "").strip().lower() != "book":
        return False
    lowered = query.lower()
    if any(re.search(rf"\b{geo}\b", lowered) for geo in _GEOS):
        return False
    if _account_in_text(query) or _OPP_RE.search(query):
        return False
    return True


def parse_scope_from_text(text: str) -> dict[str, str]:
    """Read geo, boat, account, and opp id out of a free-text RevOps ask."""
    lowered = text.lower()
    geo = ""
    for name in _GEOS:
        if re.search(rf"\b{name}\b", lowered):
            geo = name
            break
    boat = next((owner for owner in _owners() if owner.lower() in lowered), "")
    opp_match = _OPP_RE.search(text)
    return {
        "geo": geo,
        "boat": boat,
        "account_name": _account_in_text(text),
        "opp_id": opp_match.group(0).upper() if opp_match else "",
    }


def coerce_scope(
    *,
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, str]:
    """Treat 'west' as a geo even if the model stuffed it into account_name."""
    inferred = parse_scope_from_text(
        " ".join((query, geo, boat, account_name, opp_id))
    )
    geo_out = geo.strip().lower() or inferred["geo"]
    boat_out = boat.strip() or inferred["boat"]
    opp_out = opp_id.strip() or inferred["opp_id"]
    account_out = account_name.strip()
    alias = _geo_alias(account_out)
    if alias and resolve_account(account_out) is None:
        geo_out = geo_out or alias
        account_out = ""
    elif not account_out:
        account_out = inferred["account_name"]
    return {
        "geo": geo_out,
        "boat": boat_out,
        "account_name": account_out,
        "opp_id": opp_out,
    }


_OPP_TO_ACCOUNT = {
    record["opp_id"]: account
    for account, records in OPPORTUNITIES.items()
    for record in records
}
_OPP_TO_ACCOUNT.update(
    {row["opp_id"]: row["account"] for row in load_opportunities().values()}
)


def territory_for(account: str) -> str:
    for territory, names in TERRITORIES.items():
        if territory != "all" and account in names:
            return territory
    return ""


def resolve_scope(
    *,
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> tuple[list[str], dict[str, Any] | None]:
    """Resolve right-rail filters to canonical accounts."""
    scope = coerce_scope(
        geo=geo,
        boat=boat,
        account_name=account_name,
        opp_id=opp_id,
        query=query,
    )
    geo = scope["geo"]
    boat = scope["boat"]
    account_name = scope["account_name"]
    opp_id = scope["opp_id"]
    accounts = list(ACCOUNTS)
    if opp_id:
        account = _OPP_TO_ACCOUNT.get(opp_id.strip())
        if account is None:
            known = ", ".join(sorted(_OPP_TO_ACCOUNT))
            return [], error(f"Opportunity '{opp_id}' was not found. Known: {known}.")
        accounts = [account]
    elif account_name.strip():
        canonical = resolve_account(account_name)
        if canonical is None:
            return [], error(
                f"Account '{account_name}' was not found. "
                f"Known accounts: {', '.join(ACCOUNTS)}."
            )
        accounts = [canonical]

    geo_key = geo.strip().lower()
    if geo_key:
        if geo_key not in TERRITORIES or geo_key == "all":
            return [], error(f"Geo '{geo}' was not found. Use west, central, south, or east.")
        allowed = set(TERRITORIES[geo_key])
        accounts = [name for name in accounts if name in allowed]

    boat_key = boat.strip()
    if boat_key:
        owners = {str(row.get("owner")) for row in ACCOUNTS.values()}
        if boat_key not in owners:
            return [], error(f"Boat '{boat}' was not found.")
        accounts = [
            name for name in accounts if ACCOUNTS[name].get("owner") == boat_key
        ]

    return accounts, None


def quote_metrics(quote: dict[str, Any]) -> dict[str, Any]:
    list_price = int(quote["list_price"])
    quoted = int(quote["quoted_price"])
    floor = int(quote["floor_price"])
    discount_pct = round(100 * (1 - quoted / list_price), 1) if list_price else 0.0
    vs_floor = quoted - floor
    return {
        **quote,
        "discount_pct": discount_pct,
        "vs_floor": vs_floor,
        "below_floor": quoted < floor,
        "geo": territory_for(str(quote["account"])),
        "boat": ACCOUNTS[str(quote["account"])]["owner"],
    }


def quotes_for(accounts: list[str]) -> list[dict[str, Any]]:
    return [
        quote_metrics(quote)
        for quote in QUOTES
        if quote["account"] in accounts
    ]


def forecast_rollup(accounts: list[str]) -> dict[str, Any]:
    rows = []
    commit = 0
    upside = 0
    missing: list[str] = []
    risks: list[str] = []
    for account in accounts:
        meta = FORECAST_META[account]
        commit += int(meta["commit"])
        upside += int(meta["upside"])
        gaps = FORECAST_GAPS.get(account) or []
        row = {
            "account": account,
            "geo": territory_for(account),
            "boat": ACCOUNTS[account]["owner"],
            "category": meta["category"],
            "commit": meta["commit"],
            "upside": meta["upside"],
            "slip_days": meta["slip_days"],
            "missing": gaps,
            "risk_level": DEAL_RISKS[account]["level"],
            "note": meta["note"],
        }
        rows.append(row)
        for gap in gaps:
            missing.append(f"{account}: {gap}")
        if DEAL_RISKS[account]["level"] in {"high", "medium"}:
            risks.append(
                f"{account} {DEAL_RISKS[account]['level']}: "
                + "; ".join(DEAL_RISKS[account]["flags"])
            )
    return {
        "accounts": rows,
        "commit_total": commit,
        "upside_total": upside,
        "coverage": len(accounts),
        "missing_data": missing,
        "risks": risks,
    }


def credit_arr_calc(account: str, extra_bookings: int = 0) -> dict[str, Any]:
    pack = CREDIT_ARR[account]
    proposed = extra_bookings or int(pack["proposed_bookings"])
    headroom = int(pack["credit_limit"]) - int(pack["open_ar"]) - proposed
    return {
        "account": account,
        "arr": pack["arr"],
        "credit_limit": pack["credit_limit"],
        "open_ar": pack["open_ar"],
        "proposed_bookings": proposed,
        "headroom": headroom,
        "hold": headroom < 0,
        "terms": pack["terms"],
        "geo": territory_for(account),
        "boat": ACCOUNTS[account]["owner"],
    }


def pricing_waterfall(account: str) -> dict[str, Any]:
    quotes = quotes_for([account])
    guard = PRICING[account]
    quote = quotes[0] if quotes else None
    list_price = int(quote["list_price"]) if quote else 0
    gpo_pct = 5 if guard.get("gpo") else 0
    std_discount = int(quote["discount_pct"]) if quote else int(guard["discount_floor_pct"])
    after_std = round(list_price * (1 - std_discount / 100)) if list_price else 0
    after_gpo = round(after_std * (1 - gpo_pct / 100)) if after_std else 0
    net = int(quote["quoted_price"]) if quote else after_gpo
    return {
        "account": account,
        "sku": guard["sku"],
        "gpo": guard["gpo"] or "none",
        "discount_floor_pct": guard["discount_floor_pct"],
        "steps": [
            {"step": "List", "amount": list_price},
            {"step": f"Standard discount {std_discount}%", "amount": after_std},
            {"step": f"GPO {gpo_pct}%" if gpo_pct else "GPO none", "amount": after_gpo},
            {"step": "Quoted net", "amount": net},
            {
                "step": f"Floor ({guard['discount_floor_pct']}%)",
                "amount": int(quote["floor_price"]) if quote else 0,
            },
        ],
        "below_floor": bool(quote and quote["below_floor"]),
        "peer_band": f"{max(guard['discount_floor_pct'] - 3, 0)}–{guard['discount_floor_pct']}%",
        "language": guard["language"],
    }


def qbr_deck(account: str) -> list[dict[str, str]]:
    meta = FORECAST_META[account]
    risk = DEAL_RISKS[account]
    credit = credit_arr_calc(account)
    return [
        {
            "title": "Cover",
            "body": f"QBR deck — {account} — owner {ACCOUNTS[account]['owner']}",
        },
        {
            "title": "The number",
            "body": (
                f"Commit ${meta['commit']:,} / upside ${meta['upside']:,} / "
                f"ARR ${credit['arr']:,}."
            ),
        },
        {
            "title": "Risk",
            "body": f"{risk['level']}: " + "; ".join(risk["flags"]),
        },
        {
            "title": "Ask",
            "body": meta["note"],
        },
    ]
