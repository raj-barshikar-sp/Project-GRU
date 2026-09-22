"""Shared helpers for the tool layer.

Two conventions apply to every tool in this package:

1. Parameters are plain strings. Gemini function calling is happiest with flat,
   required arguments, so optional filters use the sentinel "all" rather than
   None or a default value.
2. Tools that carry numbers return rendered markdown. The agent receives a
   finished table and narrates it, which is the whole point of keeping
   arithmetic out of the model.
"""

from __future__ import annotations

from mktg_core.connectors import Connectors, get_connectors
from mktg_core.contracts import Region

REGION_HELP = 'One of "AMER", "EMEA", "APJ", or "all" for every region.'


def conn() -> Connectors:
    return get_connectors()


def parse_region(value: str) -> Region | None:
    """Turn a region argument into a Region, or None meaning no filter.

    Deliberately forgiving about case and whitespace: the value often comes
    straight from something a user typed.
    """
    cleaned = (value or "all").strip().lower()
    if cleaned in {"all", "", "global", "worldwide", "any"}:
        return None
    for region in Region:
        if cleaned == region.value.lower():
            return region
    raise ValueError(
        f"Unknown region {value!r}. Use AMER, EMEA, APJ or all."
    )
