"""Final Sales Manager-facing synthesis payload."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    """One next step the manager can take, with optional paste-ready text."""

    action: str = Field(description="What to do, in one sentence.")
    owner: str = Field(default="you", description="Who does it.")
    due: str = Field(default="", description="Date or window if known.")
    paste: str = Field(
        default="",
        description="Short line the manager can copy into Slack or a meeting note.",
    )


class CopyReadyArtifact(BaseModel):
    """A block the manager can paste into email, CRM, or a doc."""

    title: str
    kind: Literal[
        "email", "merge_instruction", "talking_points", "ask", "work_order", "other"
    ] = "other"
    body: str = Field(description="Full paste-ready text. No placeholders like [NAME].")


class SynthesisOutput(BaseModel):
    """Merged, personalized answer produced by the synthesis agent."""

    summary: str = Field(description="Short briefing of the situation and ask.")
    insights: list[str] = Field(
        default_factory=list,
        description="The most important takeaways for the sales manager.",
    )
    actions: list[RecommendedAction] = Field(
        default_factory=list,
        description="Concrete next steps, each with optional paste text.",
    )
    artifacts: list[CopyReadyArtifact] = Field(
        default_factory=list,
        description="Emails, merge instructions, asks, and other paste-ready blocks.",
    )


def _action_line(index: int, action: dict[str, object]) -> list[str]:
    body = str(action.get("action") or "").strip()
    if not body:
        return []
    owner = str(action.get("owner") or "you").strip()
    due = str(action.get("due") or "").strip()
    metadata = ", ".join(
        part
        for part in (
            f"owner: {owner}" if owner else "",
            f"when: {due}" if due else "",
        )
        if part
    )
    lines = [f"{index}. {body}{f' ({metadata})' if metadata else ''}"]
    paste = str(action.get("paste") or "").strip()
    if paste:
        lines.append(f"   Paste: {paste}")
    return lines


def render_synthesis_markdown(output: SynthesisOutput) -> str:
    """Render the validated schema into the manager-facing markdown shape."""
    insights = "\n".join(f"- {item.strip()}" for item in output.insights)
    if not insights:
        insights = "- No additional account-changing insight was identified."

    action_lines: list[str] = []
    for index, action in enumerate(output.actions, start=1):
        action_lines.extend(_action_line(index, action.model_dump()))
    actions = "\n".join(action_lines) or "1. Confirm the next step with the account."

    artifact_lines: list[str] = []
    for artifact in output.artifacts:
        artifact_lines.extend(
            [
                f"### {artifact.title.strip()}",
                "```",
                artifact.body.strip(),
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
