"""Deliverable shapes for the ABM multi-channel package.

An agent decides what to say and emits one of these as JSON; Python renders it
to a file people can actually use (a Marketo-ready CSV, a markdown one-pager).
This is the same split as `DeckSpec -> .pptx`: the model does the words, the
code does the format, and the structure stays inspectable and testable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Email cadence (Marketo-ready) ---------------------------------------

class EmailStep(BaseModel):
    touch_number: int
    day: int  # days after the previous touch / campaign start
    subject: str
    body: str
    cta: str


class EmailCadence(BaseModel):
    """A multi-touch email sequence for one persona at one account."""

    account: str
    persona: str
    steps: list[EmailStep] = Field(default_factory=list)

    def to_csv_rows(self) -> list[dict[str, str]]:
        """Flat rows Marketo can import: one row per touch."""
        return [
            {
                "Account": self.account,
                "Persona": self.persona,
                "Touch": str(s.touch_number),
                "Send Day": str(s.day),
                "Subject": s.subject,
                "Body": s.body,
                "CTA": s.cta,
            }
            for s in self.steps
        ]

    def to_markdown(self) -> str:
        lines = [f"## Email cadence - {self.persona} @ {self.account}", ""]
        for s in self.steps:
            lines += [
                f"### Touch {s.touch_number} (day {s.day})",
                f"**Subject:** {s.subject}",
                "",
                s.body,
                "",
                f"**CTA:** {s.cta}",
                "",
            ]
        return "\n".join(lines)


# --- LinkedIn outreach ----------------------------------------------------

class LinkedInStep(BaseModel):
    step_number: int
    kind: str  # "connection", "inmail", "follow_up"
    day: int
    message: str


class LinkedInSequence(BaseModel):
    account: str
    persona: str
    steps: list[LinkedInStep] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"## LinkedIn sequence - {self.persona} @ {self.account}", ""]
        for s in self.steps:
            lines += [
                f"### Step {s.step_number}: {s.kind} (day {s.day})",
                s.message,
                "",
            ]
        return "\n".join(lines)


# --- Folloze ABM board ----------------------------------------------------

class FollozeContentModule(BaseModel):
    module_type: str  # video, case_study, product_brief, whitepaper
    title: str
    asset_ref: str = ""
    why_it_fits: str = ""


class FollozeBoardSpec(BaseModel):
    account: str
    banner_headline: str
    banner_subtext: str
    cta: str
    modules: list[FollozeContentModule] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"## Folloze board - {self.account}",
            "",
            f"**Banner:** {self.banner_headline}",
            f"_{self.banner_subtext}_",
            "",
            f"**Primary CTA:** {self.cta}",
            "",
            "### Content modules",
            "",
            "| Type | Title | Asset | Why it fits |",
            "|---|---|---|---|",
        ]
        for m in self.modules:
            lines.append(
                f"| {m.module_type} | {m.title} | {m.asset_ref or '-'} "
                f"| {m.why_it_fits or '-'} |"
            )
        return "\n".join(lines)


# --- Sales playbook -------------------------------------------------------

class SalesPlaybook(BaseModel):
    account: str
    summary: str
    key_stakeholders: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    talk_tracks: list[str] = Field(default_factory=list)
    competitive_landmines: list[str] = Field(default_factory=list)
    recommended_assets: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        def section(title: str, items: list[str]) -> list[str]:
            if not items:
                return []
            return [f"### {title}", ""] + [f"- {i}" for i in items] + [""]

        lines = [f"## Sales playbook - {self.account}", "", self.summary, ""]
        lines += section("Key stakeholders", self.key_stakeholders)
        lines += section("Pain points", self.pain_points)
        lines += section("Talk tracks", self.talk_tracks)
        lines += section("Competitive landmines", self.competitive_landmines)
        lines += section("Recommended assets", self.recommended_assets)
        return "\n".join(lines)
