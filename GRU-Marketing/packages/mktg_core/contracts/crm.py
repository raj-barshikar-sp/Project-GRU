"""The CRM and marketing-system objects shared by all seven orchestrators.

These are deliberately narrower than the real Salesforce/Marketo schemas. They
carry the fields the agents actually reason about and nothing else.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

# The fixture world is frozen at this date so metrics and tests are
# deterministic. Real connectors would use date.today().
AS_OF = date(2026, 9, 4)


class Region(StrEnum):
    AMER = "AMER"
    EMEA = "EMEA"
    APJ = "APJ"


class OppStage(StrEnum):
    """Ordered pipeline stages. Order matters for funnel maths."""

    STAGE_1_DISCOVERY = "1-Discovery"
    STAGE_2_QUALIFY = "2-Qualify"
    STAGE_3_VALIDATE = "3-Validate"
    STAGE_4_PROPOSE = "4-Propose"
    STAGE_5_NEGOTIATE = "5-Negotiate"
    CLOSED_WON = "Closed Won"
    CLOSED_LOST = "Closed Lost"


OPEN_STAGES: tuple[OppStage, ...] = (
    OppStage.STAGE_1_DISCOVERY,
    OppStage.STAGE_2_QUALIFY,
    OppStage.STAGE_3_VALIDATE,
    OppStage.STAGE_4_PROPOSE,
    OppStage.STAGE_5_NEGOTIATE,
)


class CampaignType(StrEnum):
    WEBINAR = "Webinar"
    FIELD_EVENT = "Field Event"
    PAID_SEARCH = "Paid Search"
    PAID_SOCIAL = "Paid Social"
    CONTENT_SYNDICATION = "Content Syndication"
    EMAIL_NURTURE = "Email Nurture"
    TRADESHOW = "Tradeshow"


class Account(BaseModel):
    id: str
    name: str
    industry: str
    region: Region
    country: str
    city: str
    employee_count: int
    annual_revenue_usd: int
    is_target_account: bool = False
    # Gainsight-style health score, 0-100. None for prospects with no product.
    health_score: int | None = None


class Contact(BaseModel):
    id: str
    account_id: str
    full_name: str
    email: str
    title: str
    seniority: str  # C-Level, VP, Director, Manager, Practitioner
    function: str  # Security, IT, Engineering, Finance, Marketing
    country: str
    # Marketing consent. The POC keeps the field so the later consent work has
    # somewhere to land, but nothing enforces it yet.
    email_opt_in: bool = True


class Opportunity(BaseModel):
    id: str
    account_id: str
    name: str
    stage: OppStage
    amount_usd: int
    created_date: date
    close_date: date
    # Which stage it was in one week ago. Lets us detect movement without
    # storing a full history.
    stage_one_week_ago: OppStage | None = None
    source_campaign_id: str | None = None
    owner_region: Region = Region.AMER

    @property
    def is_open(self) -> bool:
        return self.stage in OPEN_STAGES

    @property
    def days_in_pipeline(self) -> int:
        return (AS_OF - self.created_date).days

    @property
    def is_stalled(self) -> bool:
        """Open, older than 60 days, and did not move stage in the last week."""
        return (
            self.is_open
            and self.days_in_pipeline > 60
            and self.stage_one_week_ago == self.stage
        )


class Campaign(BaseModel):
    id: str
    name: str
    type: CampaignType
    region: Region
    start_date: date
    end_date: date
    spend_usd: int
    # Funnel counts, measured to date.
    impressions: int = 0
    clicks: int = 0
    leads: int = 0
    mqls: int = 0
    sqls: int = 0
    opps_created: int = 0
    # Snapshot of the same counts one week ago, for week-over-week trends.
    leads_one_week_ago: int = 0
    mqls_one_week_ago: int = 0
    opps_created_one_week_ago: int = 0


class IntentSignal(BaseModel):
    """A 6sense-style buying signal on an account."""

    account_id: str
    keyword: str
    intent_score: int = Field(ge=0, le=100)
    # None, Awareness, Consideration, Decision, Purchase
    buying_stage: str
    trending: bool = False


class EngagementEvent(BaseModel):
    """A Marketo-style touchpoint: someone at an account consumed an asset."""

    contact_id: str
    account_id: str
    asset_id: str
    asset_name: str
    asset_type: str  # Whitepaper, Webinar, Demo, Case Study, Blog, Event
    occurred_on: date
    campaign_id: str | None = None


class EventAttendee(BaseModel):
    """A registration for a regional field event."""

    event_id: str
    contact_id: str
    account_id: str
    status: str  # Registered, Confirmed, Attended, No Show


class FieldEvent(BaseModel):
    id: str
    name: str
    city: str
    region: Region
    event_date: date
    topic: str
