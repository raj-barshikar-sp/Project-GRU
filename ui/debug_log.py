"""Pretty-print Bob debug traces to logs/bob.log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "bob.log"


def write(kind: str, payload: dict[str, Any]) -> Path:
    """Append one indented JSON block. Terminal only gets a one-line pointer."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    block = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        **payload,
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(block, indent=2, ensure_ascii=False, default=str))
        handle.write("\n\n")
    print(f"[bob] {kind} → {LOG_PATH}", flush=True)
    return LOG_PATH
