"""The shape every calculation returns.

`MetricTable` is the contract between the maths and the agents. A metrics
function computes one, and the agent receives it rendered as markdown and
explains it. The agent never recomputes anything in the table.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def _fmt(value: Any) -> str:
    """Render a cell for the model: money and percentages made readable."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    if value is None:
        return "-"
    return str(value)


class MetricTable(BaseModel):
    """A finished calculation, ready for an agent to narrate.

    `notes` is where the calculation explains itself: definitions, thresholds
    used, anything the agent would otherwise be tempted to guess at.
    """

    name: str
    description: str
    columns: list[str]
    rows: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        """What the agent actually sees. Markdown reads reliably to an LLM."""
        lines = [f"### {self.name}", "", self.description, ""]
        if not self.rows:
            lines.append("_No rows matched._")
        else:
            lines.append("| " + " | ".join(self.columns) + " |")
            lines.append("|" + "|".join(["---"] * len(self.columns)) + "|")
            for row in self.rows:
                lines.append(
                    "| " + " | ".join(_fmt(row.get(c)) for c in self.columns) + " |"
                )
        if self.notes:
            lines += ["", "Notes:"] + [f"- {n}" for n in self.notes]
        return "\n".join(lines)


class MetricBundle(BaseModel):
    """Several tables handed over together, e.g. everything a deck needs."""

    tables: list[MetricTable] = Field(default_factory=list)

    def to_markdown(self) -> str:
        return "\n\n".join(t.to_markdown() for t in self.tables)
