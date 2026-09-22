"""Turning agent JSON deliverables into files people can open."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import ValidationError

from ..contracts import (
    AnchorAsset,
    AssetGrid,
    Battlecard,
    CampaignBrief,
    EmailCadence,
    FollozeBoardSpec,
    LinkedInSequence,
    LocalizedAsset,
    RapidResponsePackage,
    SalesPlaybook,
)

OUTPUT_DIR = Path("output")


def _ensure_dir(subdir: str) -> Path:
    path = OUTPUT_DIR / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_markdown(content: str, filename: str, subdir: str = "artifacts") -> Path:
    directory = _ensure_dir(subdir)
    path = directory / markdown_filename(filename)
    path.write_text(content)
    return path


def markdown_filename(filename: str) -> str:
    """Keep one .md suffix even when the model passes a .json name."""
    name = Path(filename or "artifact").name.strip() or "artifact"
    lowered = name.lower()
    for suffix in (".json.md", ".md.json", ".json", ".md"):
        if lowered.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f"{name}.md"


def describe_saved(result: Path | str) -> str:
    """Return a tool reply the UI can show: path plus the file when it is markdown."""
    if isinstance(result, str):
        return result
    rel = result.as_posix()
    if result.suffix.lower() != ".md":
        return f"Saved to {rel}"
    return f"Saved to {rel}\n\n{result.read_text()}"


def save_email_cadence_csv(cadence_json: str, filename: str) -> Path | str:
    try:
        cadence = EmailCadence.model_validate(json.loads(cadence_json))
    except (json.JSONDecodeError, ValidationError) as exc:
        return f"Could not parse email cadence JSON: {exc}"

    directory = _ensure_dir("abm")
    if not filename.endswith(".csv"):
        filename += ".csv"
    path = directory / filename
    rows = cadence.to_csv_rows()
    if not rows:
        return "Email cadence has no steps."
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_artifact(artifact_json: str, artifact_type: str,
                  filename: str) -> Path | str:
    """Render a typed deliverable to markdown (or CSV for email cadences)."""
    try:
        payload = json.loads(artifact_json)
    except json.JSONDecodeError as exc:
        return f"Could not parse JSON: {exc}"

    type_map = {
        "email_cadence": (EmailCadence, "abm", lambda o: o.to_markdown()),
        "linkedin": (LinkedInSequence, "abm", lambda o: o.to_markdown()),
        "folloze": (FollozeBoardSpec, "abm", lambda o: o.to_markdown()),
        "playbook": (SalesPlaybook, "abm", lambda o: o.to_markdown()),
        "campaign_brief": (CampaignBrief, "campaign", lambda o: _brief_md(o)),
        "battlecard": (Battlecard, "campaign", lambda o: _battlecard_md(o)),
        "anchor_asset": (AnchorAsset, "content", lambda o: _anchor_md(o)),
        "asset_grid": (AssetGrid, "content", lambda o: _grid_md(o)),
        "localized": (LocalizedAsset, "content", lambda o: _localized_md(o)),
        "rapid_response": (RapidResponsePackage, "brand",
                           lambda o: _rapid_response_md(o)),
    }

    if artifact_type == "email_cadence":
        return save_email_cadence_csv(artifact_json, filename)

    if artifact_type not in type_map:
        return f"Unknown artifact type {artifact_type!r}."

    model_cls, subdir, renderer = type_map[artifact_type]
    try:
        obj = model_cls.model_validate(payload)
    except ValidationError as exc:
        return f"JSON did not match {artifact_type} shape: {exc}"

    content = renderer(obj)
    return save_markdown(content, filename, subdir)


def _brief_md(b: CampaignBrief) -> str:
    lines = [f"# Campaign brief: {b.name}", "", f"**Goal:** {b.goal}",
             f"**Audience:** {b.target_audience}",
             f"**Budget:** ${b.budget_usd:,}", f"**Timeline:** {b.timeline}", ""]
    if b.key_messages:
        lines += ["## Key messages", ""] + [f"- {m}" for m in b.key_messages] + [""]
    if b.channels:
        lines += ["## Channels", ""] + [f"- {c}" for c in b.channels] + [""]
    if b.kpis:
        lines += ["## KPIs", ""] + [f"- {k}" for k in b.kpis] + [""]
    return "\n".join(lines)


def _battlecard_md(b: Battlecard) -> str:
    lines = [f"# Battlecard: SailPoint vs {b.competitor}", "",
             b.positioning_statement, ""]
    lines += ["## Why we win", ""] + [f"- {w}" for w in b.why_we_win] + [""]
    lines += ["## Their strengths", ""] + [f"- {s}" for s in b.their_strengths] + [""]
    lines += ["## Landmines", ""] + [f"- {l}" for l in b.landmines] + [""]
    if b.objection_handlers:
        lines += ["## Objection handlers", ""]
        for oh in b.objection_handlers:
            lines += [f"**{oh.objection}**", oh.response, ""]
    if b.displacement_cta:
        lines += [f"**CTA:** {b.displacement_cta}"]
    return "\n".join(lines)


def _anchor_md(a: AnchorAsset) -> str:
    lines = [f"# {a.title}", f"*{a.asset_type} | {a.audience}*", "",
             "## Executive summary", a.executive_summary, ""]
    for sec in a.sections:
        lines += [f"## {sec.heading}", sec.body, ""]
    if a.cta:
        lines += [f"**CTA:** {a.cta}"]
    return "\n".join(lines)


def _grid_md(g: AssetGrid) -> str:
    lines = [f"# Asset grid from: {g.source_asset}", "",
             "| Channel | Format | Headline |",
             "|---|---|---|"]
    for item in g.items:
        lines.append(f"| {item.channel} | {item.format} | {item.headline} |")
    return "\n".join(lines)


def _localized_md(l: LocalizedAsset) -> str:
    lines = [f"# {l.title}", f"*{l.language} | {l.region}*", "", l.body, ""]
    if l.localization_notes:
        lines += ["## Localization notes", ""] + [
            f"- {n}" for n in l.localization_notes]
    return "\n".join(lines)


def _rapid_response_md(p: RapidResponsePackage) -> str:
    lines = [f"# Rapid response: {p.trigger}", "", f"**Angle:** {p.angle}", ""]
    if p.social_posts:
        lines += ["## Social posts", ""] + [f"- {s}" for s in p.social_posts] + [""]
    if p.blog_outline:
        lines += ["## Blog outline", ""] + [f"- {b}" for b in p.blog_outline] + [""]
    if p.email_alert_subject:
        lines += ["## Email alert", f"**Subject:** {p.email_alert_subject}",
                  p.email_alert_body, ""]
    if p.ad_copy:
        lines += ["## Ad copy", ""] + [f"- {a}" for a in p.ad_copy] + [""]
    if p.executive_quote:
        lines += [f"**Executive quote:** {p.executive_quote}"]
    return "\n".join(lines)
