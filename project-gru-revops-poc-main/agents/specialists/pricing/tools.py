"""Pricing analytics waterfall."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import pricing_waterfall, resolve_scope
from agents.tooling import error, success
from agents.tooling import tool


@tool
async def run_pricing_analytics(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """Build a pricing waterfall versus floor for the first in-scope account.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err = resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id
    )
    if err:
        return err
    if not accounts:
        return error("Pricing analytics needs an account, opp, geo, or boat.")
    pack = pricing_waterfall(accounts[0])
    waterfall = [
        f"{step['step']}: ${step['amount']:,}" for step in pack["steps"]
    ]
    copy = [
        f"{pack['account']} {pack['sku']}: net vs floor "
        f"{'BELOW FLOOR' if pack['below_floor'] else 'within floor'}; "
        f"peer band {pack['peer_band']}."
    ]
    return success({**pack, "waterfall": waterfall, "copy_ready": copy})
