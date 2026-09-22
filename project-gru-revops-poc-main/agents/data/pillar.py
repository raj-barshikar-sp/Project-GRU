"""Mock deal, extra-opp, and list/floor facts used by RevOps calculators."""

from __future__ import annotations

from typing import Any

EXTRA_OPPORTUNITIES: dict[str, list[dict[str, Any]]] = {
    "7-Eleven": [
        {
            "opp_id": "OPP-712",
            "name": "Project Phoenix — EV charging store systems",
            "aliases": ["Project Phoenix", "Phoenix", "EV charging"],
            "amount": 890000,
            "stage": "Discovery",
            "close_date": "2027-02-28",
            "type": "New",
            "forecast_category": "pipeline",
        }
    ],
    "Acme Corp": [
        {
            "opp_id": "OPP-242",
            "name": "Project Phoenix — plant telemetry",
            "aliases": ["Project Phoenix", "Phoenix"],
            "amount": 220000,
            "stage": "Qualification",
            "close_date": "2027-03-30",
            "type": "New",
            "forecast_category": "pipeline",
        }
    ],
}

DEAL_RISKS: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "risk_score": 32,
        "level": "low",
        "flags": ["Franchisee not in stakeholder map", "Two live opportunities share the AE"],
        "stalled_days": 0,
        "missing_champion": False,
    },
    "Acme Corp": {
        "risk_score": 61,
        "level": "medium",
        "flags": ["Close date slipped 21 days", "No IT owner", "Payback objection unpaid"],
        "stalled_days": 21,
        "missing_champion": False,
    },
    "GlobalTech": {
        "risk_score": 48,
        "level": "medium",
        "flags": ["New CISO", "Renewal and expansion collide"],
        "stalled_days": 0,
        "missing_champion": False,
    },
    "NovaPay": {
        "risk_score": 88,
        "level": "high",
        "flags": ["11 months dark", "Bounced exec still Active", "No economic buyer"],
        "stalled_days": 330,
        "missing_champion": True,
    },
    "Meridian Health": {
        "risk_score": 40,
        "level": "medium",
        "flags": ["RFP due 2026-09-05", "Privacy can block the demo"],
        "stalled_days": 0,
        "missing_champion": False,
    },
    "BrightLeaf Foods": {
        "risk_score": 55,
        "level": "medium",
        "flags": ["Three-vendor bake-off", "Broken CRM artifact"],
        "stalled_days": 14,
        "missing_champion": False,
    },
    "Helix Robotics": {
        "risk_score": 58,
        "level": "medium",
        "flags": ["Duplicate champion contact", "Website blank", "Still in qualification"],
        "stalled_days": 7,
        "missing_champion": False,
    },
}

PRICING: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "sku": "StoreOps + Inventory Sync expansion",
        "discount_floor_pct": 12,
        "gpo": None,
        "language": "Pilot is 50 stores. Expansion pricing only after tabletop success.",
        "do_not": "Do not give franchisee-wide pricing in the first meeting.",
    },
    "Acme Corp": {
        "sku": "Quote-to-Cash, Dayton site",
        "discount_floor_pct": 8,
        "gpo": None,
        "language": "Fixed-price Oracle connector. Capped professional services.",
        "do_not": "Do not open enterprise-wide licensing.",
    },
    "GlobalTech": {
        "sku": "Partner Portal APAC seats",
        "discount_floor_pct": 10,
        "gpo": None,
        "language": "Singapore region included on the expansion SKU.",
        "do_not": "Do not trade security review time for extra discount.",
    },
    "NovaPay": {
        "sku": "Paid diagnostic — one payout rail",
        "discount_floor_pct": 0,
        "gpo": None,
        "language": "Diagnostic is paid. Platform buy is a later conversation.",
        "do_not": "Do not discount a full platform to reopen a lost eval.",
    },
    "Meridian Health": {
        "sku": "Care analytics expansion",
        "discount_floor_pct": 15,
        "gpo": "Vizient",
        "language": "GPO/Vizient language ready. Do not improvise discounting.",
        "do_not": "Do not quote net of GPO without Tom in the thread.",
    },
    "BrightLeaf Foods": {
        "sku": "Trade Promotion Intelligence",
        "discount_floor_pct": 10,
        "gpo": None,
        "language": "3-year option with a 12-month opt-out and a usage collar.",
        "do_not": "Do not lock 3 years with no collar.",
    },
    "Helix Robotics": {
        "sku": "Americas GTM land",
        "discount_floor_pct": 5,
        "gpo": None,
        "language": "Quote in EUR. Frankfurt residency as a contractual exhibit.",
        "do_not": "Do not quote USD-only.",
    },
}
