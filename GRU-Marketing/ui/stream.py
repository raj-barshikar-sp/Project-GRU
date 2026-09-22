"""Split model text into word-sized SSE deltas."""

from __future__ import annotations

import re

_WORD = re.compile(r"\S+\s*")


def word_deltas(text: str) -> list[str]:
    """Return visible chunks so the UI can reveal the reply word by word."""
    if not text:
        return []
    leading = re.match(r"^\s+", text)
    chunks = _WORD.findall(text)
    if leading and chunks:
        return [leading.group(0), *chunks]
    return chunks or [text]
