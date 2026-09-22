"""Session memory for the manager's live account, territory, and opportunity."""

from __future__ import annotations

import re
from typing import Any

from agents.new_data_store import (
    accounts,
    list_accounts,
    resolve_account,
    territories,
)

SESSION_KEYS = ("ae_name", "last_account", "last_territory", "last_opportunity")
ACCOUNTS = accounts()
TERRITORIES = territories()


def seed_session_state(callback_context: Any) -> None:
    """Guarantee placeholder keys exist so instruction injection does not fail."""
    for key in SESSION_KEYS:
        if not callback_context.state.get(key):
            callback_context.state[key] = ""


def seed_context_from_text(state: Any, text: str) -> dict[str, str]:
    """Capture account and territory before routing starts."""
    return apply_working_context(
        state,
        account=detect_account_in_text(text) or "",
        territory=detect_territory_in_text(text) or "",
    )


def detect_account_in_text(text: str) -> str | None:
    """Return a canonical account mentioned in free text, if any."""
    if not text.strip():
        return None
    # Prefer longer names so "7-Eleven" wins over a partial.
    ranked = sorted(list_accounts(), key=len, reverse=True)
    lowered = text.lower()
    for name in ranked:
        if name.lower() in lowered:
            return name
        record = ACCOUNTS[name]
        for alias in [record.get("legal_name", ""), *record.get("aliases", [])]:
            if alias and str(alias).lower() in lowered:
                return name
    for token in text.replace(",", " ").split():
        resolved = resolve_account(token)
        if resolved:
            return resolved
    return None


def detect_territory_in_text(text: str) -> str | None:
    lowered = text.lower()
    for territory in ("west", "central", "south", "east"):
        if re.search(rf"\b{territory}\b", lowered):
            return territory
    return None


def _territory_for_account(account: str) -> str:
    for territory, names in TERRITORIES.items():
        if territory != "all" and account in names:
            return territory
    return ""


def apply_working_context(
    state: Any,
    *,
    account: str = "",
    territory: str = "",
    ae_name: str = "",
    opportunity: str = "",
) -> dict[str, str]:
    """Write known context onto session state. Empty strings are ignored."""
    if account:
        canonical = resolve_account(account) or account
        state["last_account"] = canonical
        if canonical in ACCOUNTS:
            state["ae_name"] = ACCOUNTS[canonical]["owner"]
            inferred = _territory_for_account(canonical)
            if inferred:
                state["last_territory"] = inferred
    if territory:
        geo = territory.strip().lower()
        if geo in TERRITORIES:
            state["last_territory"] = geo
    if ae_name:
        state["ae_name"] = ae_name
    if opportunity:
        state["last_opportunity"] = opportunity
    return {
        "ae_name": str(state.get("ae_name") or ""),
        "last_account": str(state.get("last_account") or ""),
        "last_territory": str(state.get("last_territory") or ""),
        "last_opportunity": str(state.get("last_opportunity") or ""),
    }
