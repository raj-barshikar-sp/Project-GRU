"""Final AE-facing synthesis payload."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    """One next step the AE can take, with optional paste-ready text."""

    action: str = Field(description="What to do, in one sentence.")
    owner: str = Field(default="you", description="Who does it.")
    due: str = Field(default="", description="Date or window if known.")
    paste: str = Field(
        default="",
        description="Short line the AE can copy into Slack or a calendar invite.",
    )


class CopyReadyArtifact(BaseModel):
    """A block the AE can paste into email, CRM, or a doc."""

    title: str
    kind: Literal["email", "merge_instruction", "talking_points", "ask", "work_order", "other"] = (
        "other"
    )
    body: str = Field(description="Full paste-ready text. No placeholders like [NAME].")


class SynthesisOutput(BaseModel):
    """Merged, personalized answer produced by the synthesis agent."""

    summary: str = Field(description="Short briefing of the situation and ask.")
    insights: list[str] = Field(
        default_factory=list,
        description="The most important takeaways for the account executive.",
    )
    actions: list[RecommendedAction] = Field(
        default_factory=list,
        description="Concrete next steps, each with optional paste text.",
    )
    artifacts: list[CopyReadyArtifact] = Field(
        default_factory=list,
        description="Emails, merge instructions, asks, and other paste-ready blocks.",
    )


_PLACEHOLDER_RE = re.compile(r"\[[A-Z][A-Z0-9_ /-]{1,40}\]")
_EMAIL_SIGNOFF_RE = re.compile(
    r"(?is)(\n(?:best regards|kind regards|sincerely),?)\s*\n(?:[^\n]+(?:\n|$))+$"
)


def strip_email_signoff(body: str) -> str:
    """Keep Best regards; drop name, title, or company lines after it."""
    text = body.replace("\r\n", "\n").rstrip()
    text = _EMAIL_SIGNOFF_RE.sub(r"\1", text).rstrip()
    return text + ("\n" if text else "")


_HOLLOW_RE = re.compile(
    r"awaiting (?:specialist|findings)|ha(?:ve|s) not (?:yet )?received|"
    r"underlying data .* not provided|ensure the orchestrator|"
    r"structured findings .* missing|"
    r"couldn't produce a reliable briefing|"
    r"findings need to be regenerated|"
    r"no specific numeric|"
    r"missing specific (?:performance )?data|"
    r"fresh (?:reporting )?pull|"
    r"not returned in the current records|"
    r"currently missing .* (?:coverage|kpi|metrics|performance)|"
    r"records to populate|"
    r"currently unavailable|"
    r"metrics .{0,80}unavailable|"
    r"no matching (?:kpi |performance )?records|"
    r"kpi records were (?:not )?returned|"
    r"no matching kpi|"
    r"completed processing|"
    r"no further outputs|"
    r"have been synthesized|"
    r"processing all requests|"
    r"provided the detailed review|"
    r"all account quote checks",
    re.IGNORECASE,
)


def validate_synthesis_output(
    output: SynthesisOutput,
    *,
    forbidden_terms: Iterable[str] = (),
) -> list[str]:
    """Return contract violations that should trigger one synthesis retry."""
    text = " ".join(
        [
            output.summary,
            *output.insights,
            *(action.action for action in output.actions),
            *(action.paste for action in output.actions),
            *(artifact.title for artifact in output.artifacts),
            *(artifact.body for artifact in output.artifacts),
        ]
    )
    errors: list[str] = []
    if not output.summary.strip():
        errors.append("summary is empty")
    if _PLACEHOLDER_RE.search(text):
        errors.append("contains bracket placeholders")
    if _HOLLOW_RE.search(text):
        errors.append("claims specialist findings are unavailable")
    lowered = text.lower()
    leaked = sorted(
        term for term in forbidden_terms if term.lower() in lowered
    )
    if leaked:
        errors.append(f"leaks internal source names: {', '.join(leaked)}")
    for artifact in output.artifacts:
        if artifact.kind != "email":
            continue
        words = len(artifact.body.split())
        if words < 90:
            errors.append("email artifact is too short")
    return errors


def render_synthesis_markdown(output: SynthesisOutput) -> str:
    """Render the validated schema into the only AE-facing markdown shape."""
    insights = "\n".join(f"- {item.strip()}" for item in output.insights)
    if not insights:
        insights = "- No additional account-changing insight was identified."

    action_lines: list[str] = []
    for index, action in enumerate(output.actions, start=1):
        metadata = ", ".join(
            part
            for part in (
                f"owner: {action.owner.strip()}" if action.owner.strip() else "",
                f"when: {action.due.strip()}" if action.due.strip() else "",
            )
            if part
        )
        suffix = f" ({metadata})" if metadata else ""
        action_lines.append(f"{index}. {action.action.strip()}{suffix}")
        if action.paste.strip():
            action_lines.append(f"   Paste: {action.paste.strip()}")
    actions = "\n".join(action_lines) or "1. Confirm the next step with the account."

    artifact_lines: list[str] = []
    for artifact in output.artifacts:
        body = artifact.body.strip()
        if artifact.kind == "email":
            body = strip_email_signoff(body).strip()
        artifact_lines.extend(
            [
                f"### {artifact.title.strip()} · {artifact.kind}",
                "```",
                body,
                "```",
            ]
        )
    artifacts = "\n".join(artifact_lines) or "None."

    return "\n\n".join(
        [
            "## Summary\n" + output.summary.strip(),
            "## Key Insights\n" + insights,
            "## Recommended Actions\n" + actions,
            "## Artifacts\n" + artifacts,
        ]
    )
