"""Deal hygiene tools over dummy Salesforce / Outlook / Kaia / Highspot rows."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import resolve_scope
from agents.data.query import inspect_hygiene
from agents.tooling import success
from agents.tooling import tool


@tool
async def inspect_deal_hygiene(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Inspect expected fields, participation, and notes for the filtered book.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
        query: Original hygiene ask.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err = resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id, query=query
    )
    if err:
        return err
    return success(inspect_hygiene(query, accounts))
