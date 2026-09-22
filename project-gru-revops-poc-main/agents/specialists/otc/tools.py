"""Credit and ARR calculator."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.constants import TOOL_LATENCY_SECONDS
from agents.data.revops import credit_arr_calc, resolve_scope
from agents.tooling import success
from agents.tooling import tool


@tool
async def calculate_credit_arr(
    geo: str = "",
    boat: str = "",
    account_name: str = "",
    opp_id: str = "",
    extra_bookings: int = 0,
) -> dict[str, Any]:
    """Calculate ARR, credit headroom, and holds for the filtered book.

    Args:
        geo: west, central, south, or east.
        boat: AE owner name.
        account_name: Optional single account.
        opp_id: Optional opportunity id.
        extra_bookings: Optional extra bookings to stress the credit check.
    """
    await asyncio.sleep(TOOL_LATENCY_SECONDS)
    accounts, err = resolve_scope(
        geo=geo, boat=boat, account_name=account_name, opp_id=opp_id
    )
    if err:
        return err
    rows = [
        credit_arr_calc(account, extra_bookings=extra_bookings)
        for account in accounts
    ]
    holds = [
        f"{row['account']} HOLD: headroom ${row['headroom']:,} on {row['terms']}"
        for row in rows
        if row["hold"]
    ]
    lines = [
        (
            f"{row['account']}: ARR ${row['arr']:,}, limit ${row['credit_limit']:,}, "
            f"AR ${row['open_ar']:,}, proposed ${row['proposed_bookings']:,}, "
            f"headroom ${row['headroom']:,}"
        )
        for row in rows
    ]
    arr_total = sum(row["arr"] for row in rows)
    headroom_total = sum(row["headroom"] for row in rows)
    copy = [
        f"OTC: ARR ${arr_total:,}, headroom ${headroom_total:,}, "
        f"{len(holds)} credit hold(s)."
    ]
    return success(
        {
            "accounts": accounts,
            "arr_total": arr_total,
            "headroom_total": headroom_total,
            "holds": holds,
            "lines": lines,
            "copy_ready": copy,
            "rows": rows,
        }
    )
