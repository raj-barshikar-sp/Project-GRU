"""ROI quantification from value-engineering benchmarks.

Every dollar figure in a gap/value map comes from here, not from the model.
"""

from __future__ import annotations

from ..connectors import Connectors
from ..contracts import MetricTable


def _calc_lever(lever: dict, employees: int, multiplier: float) -> int:
    params = lever.get("params", {})
    hours = params.get("hours_per_1k_employees_per_year", 0)
    reduction = params.get("reduction_pct", 0)
    hourly = params.get("loaded_hourly_cost", 0)
    if hours:
        return int(employees / 1000 * hours * reduction * hourly * multiplier)
    # Breach-risk model.
    breach_cost = params.get("avg_breach_cost_usd", 0)
    prob = params.get("annual_probability", 0)
    red = params.get("reduction_pct", 0)
    return int(breach_cost * prob * red * multiplier)


def gap_value_map(conn: Connectors, account_id: str) -> MetricTable:
    """Map account technographic gaps to SailPoint capabilities with ROI."""
    accounts = {a.id: a for a in conn.sfdc.list_accounts()}
    account = accounts.get(account_id)
    if account is None:
        return MetricTable(
            name="Gap and value map",
            description=f"No account found with id {account_id!r}.",
            columns=["Gap", "Capability", "Annual value (USD)"],
            rows=[],
        )

    benchmarks = conn.kb.get_icp()  # fallback
    try:
        from ..connectors._fixtures import load
        benchmarks = load("value_benchmarks.json")
    except FileNotFoundError:
        pass

    levers = benchmarks.get("levers", {})
    multipliers = benchmarks.get("industry_multipliers", {})
    mult = multipliers.get(account.industry, 1.0)

    tech = conn.enrichment.list_technographics([account_id])
    features = conn.kb.list_product_features()

    gaps: list[tuple[str, str, str]] = []
    for t in tech:
        status = (t.status or "").lower()
        vendor = t.vendor.lower()
        if status in {"legacy", "end-of-life", "homegrown", "manual"}:
            gaps.append((f"{t.category}: {t.vendor} ({t.status})",
                         "legacy IGA gap", "access_review_automation"))
        elif vendor == "cyberark" and t.category == "PAM":
            gaps.append((f"PAM without governance ({t.vendor})",
                         "governance gap", "access_review_automation"))

    if not gaps:
        gaps.append(("No modern IGA platform detected",
                     "identity governance", "provisioning_efficiency"))

    rows = []
    matched_features = set()
    for gap_desc, gap_type, lever_key in gaps:
        lever = levers.get(lever_key, {})
        annual = _calc_lever(lever, account.employee_count, mult) if lever else 0
        feature = next(
            (f for f in features if f.value_driver == lever_key
             or lever_key in f.addresses_gap.lower()),
            features[0] if features else None,
        )
        cap = feature.capability if feature else "Identity Security Cloud"
        if feature:
            matched_features.add(feature.id)
        rows.append({
            "Gap": gap_desc,
            "SailPoint capability": cap,
            "Value lever": lever.get("metric", lever_key),
            "Annual value (USD)": annual,
        })

    total = sum(r["Annual value (USD)"] for r in rows)
    return MetricTable(
        name=f"Gap and value map - {account.name}",
        description=(
            f"Technology gaps at {account.name} mapped to SailPoint capabilities."
        ),
        columns=["Gap", "SailPoint capability", "Value lever",
                 "Annual value (USD)"],
        rows=rows,
        notes=[
            f"Total quantified annual value: ${total:,}.",
            f"Industry multiplier for {account.industry}: {mult}x.",
            "Values computed from value_benchmarks.json, not estimated by the model.",
        ],
    )
