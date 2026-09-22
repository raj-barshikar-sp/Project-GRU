"""Grouping accounts by place and by what they are researching.

This is the deterministic half of the "where should we run an event" question.
The clustering and counting happen here; deciding which cluster is the better
bet, and what the session should be called, is the agent's job.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable, Region


def accounts_without_opportunity(
    conn: Connectors, region: Region | None = None
) -> MetricTable:
    """Accounts with no opportunity at all, grouped by city.

    A city only becomes an event candidate if enough unworked accounts sit
    there, so the count per city is the whole point of this table.
    """
    accounts = conn.sfdc.list_accounts(region)
    with_opp = {o.account_id for o in conn.sfdc.list_opportunities()}
    signals = conn.sixsense.list_intent_signals()

    intent_by_account: dict[str, list] = {}
    for signal in signals:
        intent_by_account.setdefault(signal.account_id, []).append(signal)

    no_opp = [a for a in accounts if a.id not in with_opp]

    by_city: dict[str, dict] = {}
    for account in no_opp:
        entry = by_city.setdefault(account.city, {
            "region": account.region.value,
            "country": account.country,
            "accounts": [],
            "keywords": {},
            "scores": [],
        })
        entry["accounts"].append(account.name)
        for signal in intent_by_account.get(account.id, []):
            entry["keywords"][signal.keyword] = (
                entry["keywords"].get(signal.keyword, 0) + 1)
            entry["scores"].append(signal.intent_score)

    rows = []
    for city, entry in by_city.items():
        top = sorted(entry["keywords"].items(), key=lambda kv: kv[1], reverse=True)
        avg_score = (int(sum(entry["scores"]) / len(entry["scores"]))
                     if entry["scores"] else 0)
        rows.append({
            "City": city,
            "Country": entry["country"],
            "Region": entry["region"],
            "Accounts with no opp": len(entry["accounts"]),
            "Avg intent score": avg_score,
            "Top intent keywords": ", ".join(f"{k} ({v})" for k, v in top[:3]) or "-",
        })

    # Cluster size first, then intent strength. A big cluster of lukewarm
    # accounts is usually a better event than two very keen ones.
    rows.sort(key=lambda r: (r["Accounts with no opp"], r["Avg intent score"]),
              reverse=True)

    return MetricTable(
        name="Unworked accounts by city",
        description=(
            f"{len(no_opp)} accounts have no opportunity"
            + (f" in {region.value}" if region else "")
            + ", grouped by city with what they are researching."
        ),
        columns=["City", "Country", "Region", "Accounts with no opp",
                 "Avg intent score", "Top intent keywords"],
        rows=rows,
        notes=[
            "Sorted by cluster size, then average intent score.",
            "Keyword counts in brackets are how many accounts in that city "
            "show the keyword.",
            "Intent scores run 0-100; above 80 is a strong signal.",
        ],
    )


def intent_themes(conn: Connectors, account_ids: list[str] | None = None,
                  min_score: int = 0) -> MetricTable:
    """Which topics a group of accounts is researching, ranked by reach."""
    signals = conn.sixsense.list_intent_signals(account_ids)
    signals = [s for s in signals if s.intent_score >= min_score]

    by_keyword: dict[str, dict] = {}
    for signal in signals:
        entry = by_keyword.setdefault(signal.keyword, {
            "accounts": set(), "scores": [], "trending": 0, "stages": {}})
        entry["accounts"].add(signal.account_id)
        entry["scores"].append(signal.intent_score)
        entry["trending"] += 1 if signal.trending else 0
        entry["stages"][signal.buying_stage] = (
            entry["stages"].get(signal.buying_stage, 0) + 1)

    rows = []
    for keyword, entry in by_keyword.items():
        common_stage = max(entry["stages"].items(), key=lambda kv: kv[1])[0]
        rows.append({
            "Keyword": keyword,
            "Accounts": len(entry["accounts"]),
            "Avg intent score": int(sum(entry["scores"]) / len(entry["scores"])),
            "Trending signals": entry["trending"],
            "Most common buying stage": common_stage,
        })
    rows.sort(key=lambda r: (r["Accounts"], r["Avg intent score"]), reverse=True)

    scope = f"{len(account_ids)} accounts" if account_ids else "all accounts"
    return MetricTable(
        name="Intent themes",
        description=f"Topics being researched across {scope}.",
        columns=["Keyword", "Accounts", "Avg intent score", "Trending signals",
                 "Most common buying stage"],
        rows=rows,
        notes=[f"Minimum intent score filter: {min_score}."] if min_score else [],
    )


def buying_committee(conn: Connectors, account_ids: list[str]) -> MetricTable:
    """Score contacts for event invitation by seniority and function.

    A fixed rubric rather than a model judgement, so the ranking is stable and
    explainable. An agent still adds value on top by reading job titles that
    do not map cleanly onto these buckets.
    """
    seniority_points = {
        "C-Level": 50, "VP": 40, "Director": 30, "Manager": 18, "Practitioner": 8}
    function_points = {
        "Security": 30, "IT": 22, "Engineering": 15, "Finance": 8, "Marketing": 2}

    accounts = {a.id: a for a in conn.sfdc.list_accounts()}
    contacts = conn.sfdc.list_contacts(account_ids)

    rows = []
    for contact in contacts:
        score = (seniority_points.get(contact.seniority, 0)
                 + function_points.get(contact.function, 0))
        account = accounts.get(contact.account_id)
        rows.append({
            "Contact": contact.full_name,
            "Title": contact.title,
            "Account": account.name if account else "-",
            "City": account.city if account else "-",
            "Seniority": contact.seniority,
            "Function": contact.function,
            "Fit score": score,
            "Email opt-in": contact.email_opt_in,
        })
    rows.sort(key=lambda r: r["Fit score"], reverse=True)

    return MetricTable(
        name="Buying committee fit",
        description=(
            f"{len(rows)} contacts across {len(account_ids)} accounts, scored "
            "for event invitation."
        ),
        columns=["Contact", "Title", "Account", "City", "Seniority", "Function",
                 "Fit score", "Email opt-in"],
        rows=rows,
        notes=[
            "Fit score = seniority points (C-Level 50, VP 40, Director 30, "
            "Manager 18, Practitioner 8) plus function points (Security 30, "
            "IT 22, Engineering 15, Finance 8, Marketing 2). Maximum 80.",
            "Email opt-in is shown for information. The POC does not enforce "
            "consent; that arrives with the real Marketo integration.",
        ],
    )
