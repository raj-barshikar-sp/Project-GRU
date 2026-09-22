"""Per-author timing for one orchestrator run.

A task-driven request walks three LlmAgent layers wired with AgentTool: the
root router picks a team, the team orchestrator picks a specialist, and the
specialist calls its function tool and writes the answer. Every hop is a model
round trip, and because AgentTool returns to its caller, the layers above the
specialist can restate the whole artifact on the way back up.

That reading comes from the code, not from measurement. This records what
actually happens so the agent tree is changed on evidence: when each author
spoke, how long the gap before it was, and how much text it emitted. Several
large emissions in one run means the artifact is being regenerated.

Off unless MKTG_TRACE is set, so the default path pays nothing.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

LOGGER = logging.getLogger("mktg.trace")

# Text this long is a real answer rather than a routing hop's empty turn.
LONG_TEXT_CHARS = 1000

_OFF = {"", "0", "false", "no"}


def tracing_enabled() -> bool:
    return os.environ.get("MKTG_TRACE", "").strip().lower() not in _OFF


def _ensure_handler() -> None:
    """Give the trace its own stderr handler.

    uvicorn configures only its own loggers, so without this the lines land
    nowhere and the trace looks broken rather than empty.
    """
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


@dataclass
class RunTrace:
    """Marks every event an ADK run emits, then reports the shape of the run."""

    label: str = ""
    started: float = field(default_factory=time.monotonic)
    marks: list[tuple[str, float, int]] = field(default_factory=list)

    def mark(self, author: str, text_length: int) -> None:
        self.marks.append((author or "?", time.monotonic() - self.started, text_length))

    def lines(self) -> list[str]:
        total = time.monotonic() - self.started
        head = f"[trace] {self.label or 'run'} total={total:.1f}s events={len(self.marks)}"
        rows = []
        previous = 0.0
        for author, at, length in self.marks:
            rows.append(
                f"[trace]   +{at:6.1f}s  gap={at - previous:5.1f}s  "
                f"{author:<34} {length:>6} chars"
            )
            previous = at
        long_texts = [item for item in self.marks if item[2] >= LONG_TEXT_CHARS]
        if len(long_texts) > 1:
            sizes = ", ".join(str(item[2]) for item in long_texts)
            rows.append(
                f"[trace]   the answer was emitted {len(long_texts)} times ({sizes} chars) "
                "— upper layers are restating it"
            )
        return [head, *rows]

    def log(self) -> None:
        if not tracing_enabled():
            return
        _ensure_handler()
        for line in self.lines():
            LOGGER.info(line)
