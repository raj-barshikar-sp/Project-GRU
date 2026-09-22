"""Shapes for the Marketing Ops write path.

Even though every write is mocked in the POC, the request and result objects
are real so that swapping in a live connector is a change of implementation
rather than a change of interface.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .crm import CampaignType, Region

# Session-state bridge used by the list-load reader when rows are already
# in session (instead of reading from dummy_data/). Keeping the key here
# avoids coupling the tool to a particular caller.
UPLOADED_LEAD_FILES_STATE = "mops_uploaded_lead_files"


class CampaignSpec(BaseModel):
    """Everything needed to create a Salesforce campaign record."""

    name: str
    type: CampaignType
    region: Region
    start_date: date
    end_date: date
    budget_usd: int
    owner_email: str
    description: str = ""


class CampaignResult(BaseModel):
    campaign_id: str
    name: str
    created: bool
    message: str


class SegmentFilter(BaseModel):
    """The filter DSL a Skill Agent produces from a plain-English request.

    This is the bridge between "fintech accounts surging on Zero Trust in EMEA"
    and a deterministic query. The agent's only job is to fill this in
    correctly; applying it is plain code.
    """

    industries: list[str] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    intent_keywords: list[str] = Field(default_factory=list)
    min_intent_score: int = 0
    min_employee_count: int = 0
    target_accounts_only: bool = False


class SegmentResult(BaseModel):
    segment_id: str
    name: str
    account_count: int
    account_ids: list[str]
    filter_summary: str


class DeploymentResult(BaseModel):
    segment_id: str
    marketo_list_id: str
    contacts_pushed: int
    message: str


class ListLoadIssue(BaseModel):
    row_number: int
    column: str
    problem: str


class ListLoadReport(BaseModel):
    """The outcome of one stage of the list-load chain."""

    stage: str
    rows_in: int
    rows_out: int
    issues: list[ListLoadIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"**{self.stage}** — {self.rows_in} rows in, {self.rows_out} rows out"
        ]
        if self.issues:
            lines.append("")
            lines.append("| Row | Column | Problem |")
            lines.append("|---|---|---|")
            for issue in self.issues[:25]:
                lines.append(
                    f"| {issue.row_number} | {issue.column} | {issue.problem} |"
                )
            if len(self.issues) > 25:
                lines.append(f"| ... | ... | and {len(self.issues) - 25} more |")
        for note in self.notes:
            lines.append(f"- {note}")
        return "\n".join(lines)
