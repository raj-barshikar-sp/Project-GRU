"""Loads and caches the sample dataset.

Every mock connector reads through here, so all seven orchestrators see one
consistent world: the same account in the pipeline analysis, the event
attendee list and the Marketo load.

The dummy data lives in a top-level `dummy_data/` folder at the repo root, so
it is easy to find and edit without digging through the package tree. Regenerate
it with `python scripts/generate_fixtures.py`.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# repo_root/packages/mktg_core/connectors/_fixtures.py -> parents[3] is repo root.
FIXTURES = Path(__file__).resolve().parents[3] / "dummy_data"


@lru_cache(maxsize=None)
def load(name: str) -> Any:
    path = FIXTURES / name
    if not path.exists():
        raise FileNotFoundError(
            f"Fixture {name} is missing. Run: python scripts/generate_fixtures.py"
        )
    return json.loads(path.read_text())


def load_csv(name: str) -> list[dict[str, str]]:
    path = FIXTURES / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture {name} is missing.")
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))
