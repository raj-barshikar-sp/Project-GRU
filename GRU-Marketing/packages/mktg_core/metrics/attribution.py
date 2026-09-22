"""Which content assets actually correlate with deals moving forward.

The honest caveat, stated in the table's own notes so the agent repeats it
rather than overclaiming: this is correlation across accounts, not proof of
causation. An asset can look influential simply because engaged accounts were
already likely to buy.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable, OppStage

# Reaching these stages counts as the deal having progressed.
PROGRESSED_STAGES = {
    OppStage.STAGE_3_VALIDATE,
    OppStage.STAGE_4_PROPOSE,
    OppStage.STAGE_5_NEGOTIATE,
    OppStage.CLOSED_WON,
}


def asset_influence(conn: Connectors) -> MetricTable:
    """For each asset: accounts touched, and how many of those progressed.

    The comparison that matters is the lift over the baseline rate. An asset
    consumed by everyone will show a decent progression rate simply because
    the average account has a decent progression rate.
    """
    events = conn.marketo.list_engagement_events()
    opps = conn.sfdc.list_opportunities()
    accounts = conn.sfdc.list_accounts()

    progressed = {o.account_id for o in opps if o.stage in PROGRESSED_STAGES}
    baseline = len(progressed) / len(accounts) if accounts else 0

    by_asset: dict[str, dict] = {}
    for event in events:
        entry = by_asset.setdefault(event.asset_id, {
            "name": event.asset_name,
            "type": event.asset_type,
            "accounts": set(),
            "contacts": set(),
        })
        entry["accounts"].add(event.account_id)
        entry["contacts"].add(event.contact_id)

    rows = []
    for asset_id, entry in by_asset.items():
        touched = entry["accounts"]
        moved = touched & progressed
        rate = len(moved) / len(touched) if touched else 0
        lift = round(rate / baseline, 2) if baseline else 0
        pipeline = sum(
            o.amount_usd for o in opps
            if o.account_id in touched and o.is_open
        )
        rows.append({
            "Asset": entry["name"],
            "Type": entry["type"],
            "Accounts touched": len(touched),
            "Contacts engaged": len(entry["contacts"]),
            "Accounts progressed": len(moved),
            "Progression rate": f"{round(100 * rate, 1)}%",
            "Lift vs baseline": f"{lift}x",
            "Open pipeline touched (USD)": pipeline,
        })

    rows.sort(key=lambda r: float(r["Lift vs baseline"].rstrip("x")), reverse=True)

    return MetricTable(
        name="Asset influence on deal progression",
        description=(
            "Content assets ranked by how strongly engagement correlates with "
            "opportunities reaching Validate or later."
        ),
        columns=["Asset", "Type", "Accounts touched", "Contacts engaged",
                 "Accounts progressed", "Progression rate", "Lift vs baseline",
                 "Open pipeline touched (USD)"],
        rows=rows,
        notes=[
            f"Baseline progression rate across all {len(accounts)} accounts: "
            f"{round(100 * baseline, 1)}%.",
            "Lift is the asset's progression rate divided by that baseline. "
            "Above 1.0x means accounts touching this asset progress more often "
            "than average.",
            "This is correlation, not causation. A high-lift asset may be "
            "attracting accounts that were already likely to progress.",
            "Progressed = has an opportunity at Validate, Propose, Negotiate "
            "or Closed Won.",
        ],
    )
