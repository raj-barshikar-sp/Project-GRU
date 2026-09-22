"""Filter-aware forecast rollup tools."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import forecast_rollup, resolve_scope
from agents.tooling import success
from agents.tooling import tool


def _scope(
    geo: str, boat: str, account_name: str, opp_id: str
) -> tuple[list[str], dict[str, Any] | None, dict[str, str]]:
    accounts, err = resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id
    )
    meta = {"geo": geo.strip().lower(), "boat": boat.strip()}
    return accounts, err, meta


@tool
async def rollup_forecast(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """Roll up commit and upside for a geo, boat, account, or opportunity.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name, for example Avery Cole.
        account_name: Optional single account.
        opp_id: Optional opportunity id such as OPP-711.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err, meta = _scope(geo, boat, account_name, opp_id)
    if err:
        return err
    pack = forecast_rollup(accounts)
    line = (
        f"RevOps forecast {meta['geo'] or meta['boat'] or 'book'}: "
        f"commit ${pack['commit_total']:,} / upside ${pack['upside_total']:,} "
        f"across {pack['coverage']} accounts."
    )
    return success({**meta, **pack, "copy_ready": [line]})


@tool
async def list_forecast_gaps(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """List missing forecast fields that block a clean number.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err, meta = _scope(geo, boat, account_name, opp_id)
    if err:
        return err
    pack = forecast_rollup(accounts)
    return success({**meta, "missing_data": pack["missing_data"], "accounts": accounts})


@tool
async def list_forecast_risks(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
) -> dict[str, Any]:
    """List forecast risk that should keep a deal out of commit.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err, meta = _scope(geo, boat, account_name, opp_id)
    if err:
        return err
    pack = forecast_rollup(accounts)
    return success({**meta, "risks": pack["risks"], "accounts": accounts})
