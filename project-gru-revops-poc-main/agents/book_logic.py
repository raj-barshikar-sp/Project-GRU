"""Derive book facts and AE replies from dummy tables and the task catalog."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from agents.data.dummy_store import load_account_health, load_accounts, load_opportunities


@lru_cache(maxsize=1)
def stage_order() -> tuple[str, ...]:
    """Sales stages that actually appear on the dummy book, in numeric order."""
    codes = {
        str(row["stage_name"]).upper()
        for row in load_opportunities().values()
        if str(row.get("stage_name") or "").upper().startswith("SS")
    }
    return tuple(sorted(codes, key=lambda code: int(code[2:])))


def join_names(names: list[str]) -> str:
    """Oxford-style list from dummy owner/CSM names."""
    clean = [str(name).strip() for name in names if str(name).strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def account_people(account: str) -> list[str]:
    """People on the account from dummy owner and CSM rows — no invented names."""
    names: list[str] = []
    for row in load_accounts():
        if row.get("account") != account:
            continue
        owner = str(row.get("owner") or "").strip()
        if owner:
            names.append(owner)
        break
    csm = str(
        (load_account_health().get(account) or {}).get("csm_name") or ""
    ).strip()
    if csm and csm not in names:
        names.append(csm)
    return names


def account_geo(account: str) -> str:
    for row in load_accounts():
        if row.get("account") == account:
            return str(row.get("geo") or "").strip()
    return ""


def agent_for_topic(topic: str) -> str:
    """Map a task-menu topic id (forecast_value, kpis, …) to its specialist."""
    from ui.catalog import GROUP_AGENT, TASK_MENU

    needle = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")
    if not needle:
        return ""
    for group in TASK_MENU:
        agent_id = GROUP_AGENT[group["id"]]
        if str(group["id"]) == needle:
            return agent_id
        if str(group["label"]).lower().replace(" ", "_") == needle:
            return agent_id
        for item in group["items"]:
            if str(item["id"]) == needle:
                return agent_id
    return ""


def capability_labels() -> list[str]:
    from ui.catalog import TASK_MENU

    return [str(group["label"]) for group in TASK_MENU]


def capability_phrase() -> str:
    labels = capability_labels()
    if not labels:
        return "RevOps"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + ", or " + labels[-1]


def empty_book_briefing(account: str = "") -> dict[str, Any]:
    who = account or "that filter"
    stages = stage_order()
    chain = " → ".join(stages) if stages else "no loaded stages"
    return {
        "summary": f"No matching rows came back for {who} on this book.",
        "insights": [f"Loaded stages are {chain}."],
        "action": f"Name a loaded account or territory and the outcome ({capability_phrase()}).",
    }


@lru_cache(maxsize=1)
def route_hints() -> dict[str, tuple[str, ...]]:
    from agents.orchestrator.prompt import load_registry
    from ui.catalog import GROUP_AGENT, TASK_MENU

    hints: dict[str, list[str]] = {}
    for entry in load_registry().get("agents", []):
        agent_id = str(entry.get("id") or "")
        if not agent_id.startswith("revops_"):
            continue
        hints[agent_id] = [str(phrase).lower() for phrase in entry.get("trigger_phrases") or []]
    for group in TASK_MENU:
        agent_id = GROUP_AGENT[group["id"]]
        extra = hints.setdefault(agent_id, [])
        group_label = str(group["label"]).lower().strip()
        if " " in group_label or "-" in group_label:
            extra.append(group_label)
        for item in group["items"]:
            label = str(item["label"]).lower().replace("-", " ")
            extra.append(label)
            extra.append(str(item["id"]).replace("_", " "))
            compact = str(item["id"]).replace("_", "")
            if len(compact) >= 4:
                extra.append(compact)
            for part in re.split(r"\{[^}]+\}", str(item.get("scoped_prompt") or "")):
                fragment = re.sub(r"\s+", " ", part.lower()).strip(" .,;:—-")
                if len(fragment) >= 10:
                    extra.append(fragment)
    return {
        agent_id: tuple(dict.fromkeys(phrase for phrase in phrases if phrase))
        for agent_id, phrases in hints.items()
    }


_TOKEN_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "what",
    "which",
    "have",
    "does",
    "into",
    "onto",
}


def _stem_tokens(agent_id: str) -> set[str]:
    stem = agent_id.removeprefix("revops_")
    bits = {stem}
    if stem.endswith("ing") and len(stem) > 4:
        root = stem[:-3]
        bits.update({root + "e", root + "es"})
    return bits


@lru_cache(maxsize=1)
def domain_tokens() -> dict[str, tuple[str, ...]]:
    from ui.catalog import GROUP_AGENT, TASK_MENU

    tokens: dict[str, set[str]] = {}
    for group in TASK_MENU:
        agent_id = GROUP_AGENT[group["id"]]
        bits = tokens.setdefault(agent_id, _stem_tokens(agent_id))
        bits.add(str(group["id"]).replace("_", " "))
        bits.add(str(group["label"]).lower())
        for item in group["items"]:
            for word in re.findall(r"[a-z0-9]+", str(item["id"])):
                if word not in _TOKEN_STOP and len(word) >= 3:
                    bits.add(word)
    return {
        agent_id: tuple(sorted(words))
        for agent_id, words in tokens.items()
    }


@lru_cache(maxsize=1)
def task_tokens() -> tuple[str, ...]:
    tokens: list[str] = []
    for phrases in route_hints().values():
        tokens.extend(phrases)
    tokens.extend(code.lower() for code in stage_order())
    tokens.extend(label.lower() for label in capability_labels())
    return tuple(dict.fromkeys(tokens))
