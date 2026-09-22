"""Parse Marketing answers into the RevOps briefing payload."""

from __future__ import annotations

import re
from pathlib import Path

from mktg_core.rendering.artifact import OUTPUT_DIR

# "## Heading" at the start of a line. "###" is deliberately excluded: it is a
# sub-heading inside a pane, most often the title above a fenced block.
_HEADING_RE = re.compile(r"^##[ \t]+(?P<title>\S.*?)[ \t]*$", re.MULTILINE)

# Fenced blocks are copied verbatim and can legitimately contain "## " lines, so
# headings found inside one must not split the reply.
_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

# A section the model filled in with a placeholder carries nothing worth a pane.
_EMPTY = {"", "none", "n/a", "nothing", "not applicable"}

# An owner or timing the model filled in to satisfy the format carries nothing.
# Dropping it here keeps the caption off the card instead of printing
# "owner: N/A · when: N/A" underneath every action.
_PLACEHOLDER = _EMPTY | {"na", "tbd", "tbc", "unknown", "-", "—", "unassigned"}


def _meta_value(value: str) -> str:
    return "" if value.strip().rstrip(".").strip().lower() in _PLACEHOLDER else value.strip()

_BRIEFING_TITLES = (
    "Summary",
    "Key Insights",
    "Recommended Actions",
    "Artifacts",
)
_BRIEFING_ALIASES = {
    "key insight": "Key Insights",
    "insights": "Key Insights",
    "actions": "Recommended Actions",
    "recommended action": "Recommended Actions",
    "artifact": "Artifacts",
}
_RECEIPT_TITLES = ("Receipt", "Assumptions", "Next step")
_FIELD_RE = re.compile(
    r"^(?P<label>Status|Id|Name|Type|Region|Dates|Budget|Segment id|List id):\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_QUESTION_HINT = re.compile(
    r"please provide|what is the |could you (give|share)|need (the |a )",
    re.IGNORECASE,
)
_CANNOT_HINT = re.compile(
    r"not supported|update .+ directly|cannot (create|update|do that)",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"^(?P<n>\d+)[.)]\s+(?P<body>.*?)(?:\s+\((?P<meta>[^)]*)\))?\s*$"
)
_ARTIFACT_RE = re.compile(
    r"^###\s+(?P<title>.+?)\s*\n```(?:[^\n]*)\n(?P<body>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
_SAVED_PATH_RE = re.compile(
    r"(?:^|\b)(?:Deck saved to|Saved to)\s+(?P<path>output[/\\][^\s`'\"]+)",
    re.IGNORECASE,
)
_PPTX_PATH_RE = re.compile(
    r"(?:`|'|\")?(?P<path>output[/\\]decks[/\\][A-Za-z0-9._-]+\.pptx)(?:`|'|\")?",
    re.IGNORECASE,
)
_BOLD_HEADING_RE = re.compile(r"^\*\*(?P<title>.+?)\*\*\s*$", re.MULTILINE)
_SAVE_CLAUSE_RE = re.compile(
    r"(?i)(?:has been generated and saved to|deck saved to|saved to)\s+"
    r"[`'\"]?output[/\\]decks[/\\][A-Za-z0-9._-]+\.pptx[`'\"]?\s*\.?"
)
_BINARY_OUTPUT = {".pptx", ".potx"}


def _headings(text: str) -> list[re.Match[str]]:
    fenced = [match.span() for match in _FENCE_RE.finditer(text)]
    return [
        match
        for match in _HEADING_RE.finditer(text)
        if not any(start <= match.start() < end for start, end in fenced)
    ]


def _is_empty(body: str) -> bool:
    return body.strip().rstrip(".").strip().lower() in _EMPTY


def _canonical_briefing_title(title: str) -> str:
    stripped = title.strip()
    if stripped in _BRIEFING_TITLES:
        return stripped
    return _BRIEFING_ALIASES.get(stripped.lower(), stripped)


def _section_bodies(text: str) -> dict[str, str] | None:
    headings = _headings(text)
    if not headings or headings[0].start() != 0:
        return None
    sections: dict[str, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end() : end].strip()
        title = match.group("title")
        if title in sections:
            return None
        if not _is_empty(body):
            sections[title] = body
    return sections


def _standard_sections(text: str) -> dict[str, str] | None:
    """Return the briefing sections, or None if this is not a briefing.

    Specialists cover different ground, so a reply carries only the sections it
    genuinely has. Only Summary is mandatory. Titles may drift slightly
    (Insights vs Key Insights) and still count.
    """
    headings = _headings(text)
    if not headings or headings[0].start() != 0:
        return None
    mapped = [_canonical_briefing_title(match.group("title")) for match in headings]
    if _canonical_briefing_title(headings[0].group("title")) != "Summary":
        return None
    if not set(mapped) <= set(_BRIEFING_TITLES):
        return None
    if mapped != [title for title in _BRIEFING_TITLES if title in mapped]:
        return None

    sections: dict[str, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[match.end() : end].strip()
        title = mapped[index]
        if _is_empty(body):
            continue
        sections[title] = body
    if "Summary" not in sections:
        return None
    return sections


def _sections_from_offset(text: str, start: int) -> dict[str, str] | None:
    if start <= 0:
        return _standard_sections(text)
    return _standard_sections(text[start:])


def _bold_briefing_sections(text: str) -> dict[str, str] | None:
    matches = [
        match
        for match in _BOLD_HEADING_RE.finditer(text)
        if _canonical_briefing_title(match.group("title")) in _BRIEFING_TITLES
    ]
    if not matches:
        return None
    start = next(
        (
            index
            for index, match in enumerate(matches)
            if _canonical_briefing_title(match.group("title")) == "Summary"
        ),
        None,
    )
    if start is None:
        return None
    matches = matches[start:]
    mapped = [_canonical_briefing_title(match.group("title")) for match in matches]
    if mapped != [title for title in _BRIEFING_TITLES if title in mapped]:
        return None
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        title = mapped[index]
        if _is_empty(body):
            continue
        sections[title] = body
    if "Summary" not in sections:
        return None
    return sections


def _briefing_sections(text: str) -> dict[str, str] | None:
    standard = _standard_sections(text)
    if standard:
        return standard
    headings = _headings(text)
    if headings and _canonical_briefing_title(headings[0].group("title")) == "Summary":
        sliced = _sections_from_offset(text, headings[0].start())
        if sliced:
            return sliced
    return _bold_briefing_sections(text)


def _plain_deck_summary(text: str) -> str:
    cleaned = _SAVE_CLAUSE_RE.sub("", text)
    cleaned = _PPTX_PATH_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"\.\s+with\s+", ", with ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() or "The PowerPoint is ready."


def _parse_insights(block: str) -> list[str]:
    return [
        line.strip()[2:].strip()
        for line in block.splitlines()
        if line.strip().startswith("- ")
    ]


def _parse_actions(block: str) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in block.splitlines():
        stripped = line.strip()
        match = _ACTION_RE.match(stripped)
        if match:
            owner = ""
            due = ""
            for part in (
                piece.strip()
                for piece in (match.group("meta") or "").split(",")
                if piece.strip()
            ):
                key, separator, value = part.partition(":")
                if not separator:
                    continue
                if key.strip().lower() == "owner":
                    owner = _meta_value(value)
                elif key.strip().lower() == "when":
                    due = _meta_value(value)
            current = {
                "action": match.group("body").strip(),
                "owner": owner,
                "due": due,
                "paste": "",
            }
            actions.append(current)
        elif current is not None and stripped.lower().startswith("paste:"):
            current["paste"] = stripped.split(":", 1)[1].strip()
    return actions


def _parse_artifacts(block: str) -> list[dict[str, str]]:
    if _is_empty(block):
        return []
    return [
        {
            "title": match.group("title").strip(),
            "body": expand_saved_artifact(match.group("body").strip()),
        }
        for match in _ARTIFACT_RE.finditer(block)
    ]


def expand_saved_artifact(body: str) -> str:
    """Replace a 'Saved to output/...' stub with the markdown that was written."""
    match = _SAVED_PATH_RE.search(body or "")
    if not match:
        return body
    path = _safe_output_file(match.group("path"))
    if path is None:
        return body
    if path.suffix.lower() in _BINARY_OUTPUT:
        return body
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return body


def _deck_downloads(text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    paths: list[str] = []
    for match in _PPTX_PATH_RE.finditer(text or ""):
        paths.append(match.group("path"))
    for match in _SAVED_PATH_RE.finditer(text or ""):
        paths.append(match.group("path"))
    for raw in paths:
        candidate = Path(raw.replace("\\", "/").strip("`'\""))
        if ".." in candidate.parts or candidate.suffix.lower() != ".pptx":
            continue
        if not candidate.parts or candidate.parts[0] != "output":
            continue
        name = candidate.name
        if name in seen:
            continue
        seen.add(name)
        items.append({
            "title": name,
            "url": f"/api/decks/{name}",
            "filename": name,
        })
    return items


def _pptx_artifacts(downloads: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "title": item["filename"],
            "kind": "pptx",
            "body": "",
            "url": item["url"],
        }
        for item in downloads
    ]


def _with_downloads(payload: dict, text: str) -> dict:
    downloads = _deck_downloads(text)
    if not downloads:
        return payload
    extra: dict = {**payload, "downloads": downloads}
    existing = list(payload.get("artifacts") or [])
    upgraded: list[dict] = []
    urls: set[str] = set()
    for item in existing:
        found = _deck_downloads(item.get("body") or "")
        if found:
            deck = found[0]
            upgraded.append(
                {
                    "title": item.get("title") or deck["filename"],
                    "kind": "pptx",
                    "body": "",
                    "url": deck["url"],
                }
            )
            urls.add(deck["url"])
            continue
        upgraded.append(item)
        if item.get("url"):
            urls.add(str(item["url"]))
    for artifact in _pptx_artifacts(downloads):
        if artifact["url"] not in urls:
            upgraded.append(artifact)
    extra["artifacts"] = upgraded
    return extra


def hydrate_reply(payload: dict) -> dict:
    artifacts = payload.get("artifacts") if payload else None
    if not artifacts:
        return payload
    updated = []
    changed = False
    for item in artifacts:
        body = item.get("body") or ""
        expanded = expand_saved_artifact(body)
        if expanded != body:
            changed = True
            updated.append({**item, "body": expanded})
        else:
            updated.append(item)
    if not changed:
        return payload
    return {**payload, "artifacts": updated}


def _safe_output_file(raw: str) -> Path | None:
    candidate = Path(raw.replace("\\", "/"))
    parts = candidate.parts
    if not parts or parts[0] != "output" or ".." in parts:
        return None
    relative = Path(*parts[1:])
    names = [relative]
    name = relative.name
    parent = relative.parent
    if name.lower().endswith(".json.md"):
        names.append(parent / f"{name[:-8]}.md")
    elif name.lower().endswith(".md"):
        names.append(parent / f"{name[:-3]}.json.md")
    root = OUTPUT_DIR.resolve()
    for item in names:
        path = (OUTPUT_DIR / item).resolve()
        if root not in path.parents and path != root:
            continue
        if path.is_file():
            return path
    return None


# Writes in this build never hit a live org. The model is told to say so, but
# it often restates the tool result as "successfully created" and leaves only
# a MOCK id. The notice is attached here so the UI can show it even when the
# prose does not.
MOCK_NOTICE = (
    "This is a mock. Nothing was written to Salesforce, Marketo or 6sense."
)
_MOCK_WRITE = re.compile(
    r"701MOCK|\bSEG-MOCK|\bMOCK:|\bwould create Salesforce|\bwould create Marketo|"
    r"\bwould create 6sense|\bwould upload .+ Marketo",
    re.IGNORECASE,
)


def mock_notice_for(text: str) -> str:
    return MOCK_NOTICE if _MOCK_WRITE.search(text or "") else ""


def _parse_receipt_fields(block: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            stripped = stripped[2:].strip()
        match = _FIELD_RE.match(stripped)
        if not match:
            continue
        label = match.group("label").title()
        if label in {"Id", "Segment Id", "List Id"}:
            label = "Id"
        if label in seen:
            continue
        seen.add(label)
        fields.append({"label": label, "value": match.group("value").strip()})
    return fields


def _id_from_text(text: str) -> str:
    match = re.search(r"701MOCK\d+|SEG-MOCK-?\d+", text, re.IGNORECASE)
    return match.group(0) if match else ""


_CAMPAIGN_TYPES = (
    "Content Syndication",
    "Field Event",
    "Paid Search",
    "Paid Social",
    "Email Nurture",
    "Tradeshow",
    "Webinar",
)


def _add_field(fields: list[dict[str, str]], label: str, value: str) -> None:
    if not value or any(item["label"] == label for item in fields):
        return
    fields.append({"label": label, "value": value})


def _enrich_receipt_fields(fields: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    found = _id_from_text(text)
    if found:
        _add_field(fields, "Id", found)
    name = re.search(
        r"(?:Salesforce campaign(?: record)?|campaign)\s+['\"]?([A-Z]{3,4}-[A-Za-z0-9][A-Za-z0-9 -]*)",
        text,
        re.IGNORECASE,
    )
    if name:
        _add_field(fields, "Name", name.group(1).strip(" '\").,"))
    type_pat = "|".join(re.escape(item) for item in _CAMPAIGN_TYPES)
    campaign_type = re.search(rf"\b({type_pat})\b", text, re.IGNORECASE)
    if campaign_type:
        _add_field(fields, "Type", campaign_type.group(1))
    region = re.search(r"\b(AMER|EMEA|APJ)\b", text)
    if region:
        _add_field(fields, "Region", region.group(1))
    dates = re.search(
        r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE
    )
    if dates:
        _add_field(fields, "Dates", f"{dates.group(1)} to {dates.group(2)}")
    budget = re.search(r"\$([0-9,]+)\s*budget|Budget:\s*([0-9,]+)\s*USD", text, re.I)
    if budget:
        amount = (budget.group(1) or budget.group(2)).replace(",", "")
        _add_field(fields, "Budget", f"{amount} USD")
    return fields


def _receipt_from_prose(text: str) -> dict:
    fields = _enrich_receipt_fields(_parse_receipt_fields(text), text)
    if not any(item["label"] == "Status" for item in fields):
        fields.insert(
            0,
            {
                "label": "Status",
                "value": "Would create. Nothing was written to a live org.",
            },
        )
    elif fields[0]["label"] != "Status":
        status = next(item for item in fields if item["label"] == "Status")
        fields = [status] + [item for item in fields if item["label"] != "Status"]
    return {
        "kind": "receipt",
        "fields": fields,
        "assumptions": [],
        "next_step": "",
        "text": text,
        "notice": MOCK_NOTICE,
    }


def _receipt_from_sections(sections: dict[str, str], source: str) -> dict:
    receipt = sections.get("Receipt", "")
    fields = _parse_receipt_fields(receipt)
    if not any(item["label"] == "Id" for item in fields):
        found = _id_from_text(source)
        if found:
            fields.insert(0, {"label": "Id", "value": found})
    if not any(item["label"] == "Status" for item in fields):
        fields.insert(
            0,
            {
                "label": "Status",
                "value": "Would create. Nothing was written to a live org.",
            },
        )
    assumptions = _parse_insights(sections.get("Assumptions", ""))
    if not assumptions and sections.get("Assumptions"):
        assumptions = [
            line.strip()
            for line in sections["Assumptions"].splitlines()
            if line.strip()
        ]
    payload = {
        "kind": "receipt",
        "fields": fields,
        "assumptions": assumptions,
        "next_step": sections.get("Next step", "").strip(),
        "text": source,
        "notice": MOCK_NOTICE,
    }
    return payload


def _split_cannot(body: str) -> dict[str, str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if len(parts) >= 3:
        return {"requested": parts[0], "why": parts[1], "instead": "\n\n".join(parts[2:])}
    if len(parts) == 2:
        return {"requested": parts[0], "why": parts[1], "instead": ""}
    return {"requested": parts[0] if parts else body.strip(), "why": "", "instead": ""}


def parse_reply(text: str) -> dict:
    """Return a typed payload: briefing, receipt, question, cannot, or plain."""
    stripped = text.strip()
    notice = mock_notice_for(stripped)
    extra = {"notice": notice} if notice else {}
    sections = _section_bodies(stripped)
    first = ""
    if sections:
        first = next(iter(sections))

    if first == "Receipt" and set(sections) <= set(_RECEIPT_TITLES):
        payload = _receipt_from_sections(sections, stripped)
    elif first == "Question":
        payload = {"kind": "question", "text": sections["Question"], **extra}
    elif first == "Cannot":
        parts = _split_cannot(sections["Cannot"])
        payload = {"kind": "cannot", **parts, "text": sections["Cannot"], **extra}
    else:
        standard = _briefing_sections(stripped)
        if standard is not None:
            payload = {
                "kind": "briefing",
                "summary": standard["Summary"],
                "insights": _parse_insights(standard.get("Key Insights", "")),
                "actions": _parse_actions(standard.get("Recommended Actions", "")),
                "artifacts": _parse_artifacts(standard.get("Artifacts", "")),
                **extra,
            }
        elif _deck_downloads(stripped):
            payload = {
                "kind": "briefing",
                "summary": _plain_deck_summary(stripped),
                "insights": [],
                "actions": [],
                "artifacts": [],
                **extra,
            }
        elif notice:
            payload = _receipt_from_prose(stripped)
        elif _CANNOT_HINT.search(stripped):
            parts = _split_cannot(stripped)
            payload = {"kind": "cannot", **parts, "text": stripped}
        else:
            if _QUESTION_HINT.search(stripped) or stripped.endswith("?"):
                payload = {"kind": "question", "text": stripped}
            else:
                payload = {"kind": "plain", "text": stripped}
    return _with_downloads(payload, stripped)
