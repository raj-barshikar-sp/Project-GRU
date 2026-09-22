"""The tool that turns an agent's slide plan into a PowerPoint file.

The agent writes JSON describing the deck; this renders it. If the JSON does
not validate, the error is handed back to the agent in plain language so it can
correct itself rather than failing the whole request.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from mktg_core.contracts import DeckSpec
from mktg_core.rendering import render_deck

DECK_SCHEMA_HINT = """
{
  "title": "Deck title",
  "subtitle": "Optional subtitle",
  "slides": [
    {
      "layout": "bullets",
      "title": "Slide title",
      "bullets": ["First point", "Second point"],
      "takeaway": "The one line the reader should remember"
    },
    {
      "layout": "table",
      "title": "Coverage by region",
      "table_columns": ["Region", "Coverage"],
      "table_rows": [["AMER", "2.39x"], ["EMEA", "1.46x"]],
      "takeaway": "EMEA is the gap"
    },
    {
      "layout": "bullets_and_table",
      "title": "Stage breakdown",
      "bullets": ["Context for the table"],
      "table_columns": ["Stage", "Value"],
      "table_rows": [["3-Validate", "$12,400,000"]]
    }
  ]
}
Valid layouts: "title", "bullets", "table", "bullets_and_table".
All table cell values must be strings.
""".strip()


def save_deck(deck_json: str, filename: str) -> str:
    """Render a slide plan into a .pptx file on disk.

    Write the whole deck as a single JSON object matching this shape:

    {schema}

    Args:
        deck_json: The deck as a JSON string.
        filename: File name for the deck, for example "pipeline-review-q3".

    Returns:
        Where the file was written, or an explanation of what was wrong with
        the JSON so you can fix it and call again.
    """
    try:
        payload = json.loads(deck_json)
    except json.JSONDecodeError as exc:
        return (f"The deck JSON could not be parsed: {exc}. "
                f"Return a single valid JSON object and nothing else.")

    try:
        spec = DeckSpec.model_validate(payload)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors()[:5])
        return (f"The deck JSON did not match the expected shape: {problems}. "
                f"Expected shape:\n{DECK_SCHEMA_HINT}")

    if not spec.slides:
        return "The deck has no slides. Add at least one before saving."

    path = render_deck(spec, filename)
    display = Path("output/decks") / path.name
    return (f"Deck saved to {display.as_posix()} with {len(spec.slides) + 1} slides "
            f"(including the title slide).")


save_deck.__doc__ = save_deck.__doc__.replace("{schema}", DECK_SCHEMA_HINT)

DECK_TOOLS = [save_deck]
