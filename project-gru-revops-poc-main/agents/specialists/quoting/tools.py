"""Filter-aware quote and bundle tools."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import BUNDLES, quotes_for, resolve_scope
from agents.tooling import success
from agents.tooling import tool


@tool
async def analyze_quote_deviations(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """Compare quoted price to list and floor for in-scope quotes.

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
    quotes = quotes_for(accounts)
    deviations = [
        (
            f"{row['quote_id']} {row['account']}: quoted ${row['quoted_price']:,} "
            f"is {row['discount_pct']}% off list, "
            f"${abs(row['vs_floor']):,} {'below' if row['below_floor'] else 'above'} floor."
        )
        for row in quotes
    ]
    return success({"quotes": quotes, "deviations": deviations})


@tool
async def validate_quote_errors(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """Return blocking quote errors for the filtered book.

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
    errors = [
        f"{row['quote_id']} {row['account']}: {item}"
        for row in quotes_for(accounts)
        for item in row["errors"]
    ]
    return success({"errors": errors, "error_count": len(errors)})


@tool
async def list_product_bundles(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """List product bundles attached to in-scope quotes.

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
    bundles = []
    for row in quotes_for(accounts):
        pack = BUNDLES[row["bundle_id"]]
        bundles.append(
            f"{row['account']} {pack['name']}: " + ", ".join(pack["skus"])
        )
    return success({"bundles": bundles})
