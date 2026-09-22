"""The current operating user -- "me".

Whenever the system needs "me", "my accounts", "my region" or a default
campaign owner, this is the person it means. In this build that is
Omkar Patil, a Senior Marketing Manager, and the data lives in
``dummy_data/me.json`` so it is easy to find and change.
"""

from __future__ import annotations

from functools import lru_cache

from .connectors._fixtures import load


@lru_cache(maxsize=1)
def current_user() -> dict[str, str]:
    """Return the current user's profile as a plain dict.

    Backed by ``dummy_data/me.json``. Regenerate with
    ``python scripts/generate_fixtures.py``.
    """
    return dict(load("me.json"))
