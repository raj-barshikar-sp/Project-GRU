"""The slide-plan contract.

An agent writes a `DeckSpec` as JSON; `mktg_core.rendering` turns it into a
.pptx file. No agent ever produces a binary. This split means the deck's
structure is inspectable and testable, and the model only has to be good at
the part it is good at: deciding what to say.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SlideLayout(StrEnum):
    TITLE = "title"
    BULLETS = "bullets"
    TABLE = "table"
    # Bullets on the left, a table on the right. Used for stage breakdowns.
    BULLETS_AND_TABLE = "bullets_and_table"


class Slide(BaseModel):
    layout: SlideLayout
    title: str
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list)
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    # The one line the reader should leave with. Rendered in the footer.
    takeaway: str | None = None


class DeckSpec(BaseModel):
    title: str
    subtitle: str = ""
    slides: list[Slide] = Field(default_factory=list)
