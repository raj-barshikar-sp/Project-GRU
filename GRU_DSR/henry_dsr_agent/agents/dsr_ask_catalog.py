"""Deterministic catalog of the seller-facing "Ask Henry" digital-sales-room actions.

This module implements :class:`DSRAskCatalogAgent`, a local-first specialist that
answers the twenty-six requests exposed by Henry's Ask surface, from cold-call
coaching through post-sales handoff and enablement FAQs.

Design rules that this module deliberately enforces:

* **Local only.** Every customer statement is read from the canonical contracts in
  ``schemas/models.py`` (``SalesforceAccount``, ``IntentSignal``, ``TechnographicIntel``,
  ``ContactPersona``, ``Battlecard``) or from a caller-supplied deal-risk result. No
  network calls, no language-model calls, and no invented customer facts.
* **Loosely typed inputs, strictly typed outputs.** Records arrive as ``Any`` so that
  Pydantic models, plain mappings, and test doubles all work; fields are read through
  :func:`henry_dsr_agent.agents.base.value` using only names that exist on the canonical
  models (including their documented compatibility aliases). Results are Pydantic models.
* **Deterministic.** Scores, rankings, money splits, and discount bands are pure
  functions of the supplied records. Nothing reads the wall clock or a random source, so
  the same inputs always render byte-identical Markdown.
* **Honest about provenance.** Sales-process content that is not a customer fact --
  stage ladders, discount guardrails, commission mechanics, rules of engagement, and
  product framing -- is rendered under an explicit "Local demo guidance" note.

Typical use::

    agent = DSRAskCatalogAgent()
    classification = agent.classify("help me practice my pitch")
    result = await agent.run(
        "help me practice my pitch",
        account=account,
        intent=intent_signal,
        technographics=intel,
        battlecards=cards,
    )
    print(result.markdown)
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Literal

from pydantic import BaseModel, Field

from .base import (
    BaseAgent,
    bool_value,
    format_money,
    format_money_compact,
    int_value,
    items_value,
    number_value,
    string_values,
    text_value,
    value,
)

__all__ = [
    "DSRAskAction",
    "DSRAskCatalogAgent",
    "DSRAskCatalogEntry",
    "DSRAskCategory",
    "DSRAskClassification",
    "DSRAskResult",
    "STAGE_LADDER",
    "next_stage",
    "stage_objective",
]


# ---------------------------------------------------------------------------
# Public identifiers
# ---------------------------------------------------------------------------


class DSRAskCategory(str, Enum):
    """Grouping used to organize the Ask catalog in seller-facing surfaces."""

    PROSPECT = "prospect"
    PLAN = "plan"
    ENGAGE = "engage"
    NEGOTIATE = "negotiate"
    POST_SALE = "post_sale"
    ENABLEMENT = "enablement"


class DSRAskAction(str, Enum):
    """Stable string identifiers for every request the Ask catalog can answer."""

    COLD_CALL_COACHING = "cold_call_coaching"
    PITCH_PRACTICE = "pitch_practice"
    TOP_PROSPECT_ACCOUNTS = "top_prospect_accounts"
    INTEL_ANALYSIS = "intel_analysis"
    MESSAGING = "messaging"
    TERRITORY_WHITESPACE = "territory_whitespace"
    TOP_UPSELL_TARGET = "top_upsell_target"
    ACCOUNT_360_HEALTHCHECK = "account_360_healthcheck"
    ACCOUNT_PLAN = "account_plan"
    DISCOVERY_PREP = "discovery_prep"
    POST_MEETING_NOTES = "post_meeting_notes"
    SUGGESTED_FOLLOW_UP = "suggested_follow_up"
    DIGITAL_SALES_ROOM = "digital_sales_room"
    DMU_EXPANSION = "dmu_expansion"
    OPPORTUNITY_PLAN = "opportunity_plan"
    BUSINESS_VALUE_ASSESSMENT = "business_value_assessment"
    COMPETITIVE_POSITIONING_DECK = "competitive_positioning_deck"
    INITIAL_QUOTE = "initial_quote"
    PROPOSAL = "proposal"
    DEAL_RISK = "deal_risk"
    QUOTE_DISCOUNT_CHECKER = "quote_discount_checker"
    CONTRACT_REVIEW = "contract_review"
    POST_SALES_HANDOFF = "post_sales_handoff"
    RULES_OF_ENGAGEMENT = "rules_of_engagement"
    COMMISSION_PLANS = "commission_plans"
    PRODUCT_OVERVIEW = "product_overview"


# ---------------------------------------------------------------------------
# Public result contracts
# ---------------------------------------------------------------------------


class DSRAskCatalogEntry(BaseModel):
    """Metadata describing one catalog action."""

    action: DSRAskAction
    category: DSRAskCategory
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=400)
    requires_account: bool
    requires_portfolio: bool
    uses_demo_policy: bool
    aliases: tuple[str, ...] = Field(min_length=1)


class DSRAskClassification(BaseModel):
    """Explainable outcome of mapping a seller request onto a catalog action."""

    action: DSRAskAction
    category: DSRAskCategory
    source: Literal["requested", "alias", "default"]
    matched_alias: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    alternatives: tuple[DSRAskAction, ...] = ()

    @property
    def is_default(self) -> bool:
        """Report whether the classifier fell back to the catalog default."""
        return self.source == "default"


class DSRAskResult(BaseModel):
    """Rendered answer for one Ask catalog action."""

    action: DSRAskAction
    category: DSRAskCategory
    title: str = Field(min_length=3, max_length=240)
    markdown: str = Field(min_length=1)
    requires_account: bool
    account_name: str | None = None
    needs_account_selection: bool = False
    data_sources: tuple[str, ...] = ()
    classification: DSRAskClassification | None = None


# ---------------------------------------------------------------------------
# Catalog definition
# ---------------------------------------------------------------------------

# (action, category, title, description, requires_account, requires_portfolio,
#  uses_demo_policy, aliases). Declaration order is also the tie-break priority
# used by the classifier when two actions match equally specific aliases.
_CATALOG_SPEC: Final[
    tuple[
        tuple[
            DSRAskAction,
            DSRAskCategory,
            str,
            str,
            bool,
            bool,
            bool,
            tuple[str, ...],
        ],
        ...,
    ]
] = (
    (
        DSRAskAction.COLD_CALL_COACHING,
        DSRAskCategory.PROSPECT,
        "Cold Call Coaching",
        "Coach a live cold call with an opener, discovery pivots, objection "
        "responses, and a scoring rubric grounded in the account record.",
        True,
        False,
        False,
        (
            "cold call coaching",
            "cold calling",
            "cold call",
            "call coaching",
            "call coach",
            "call opener",
            "phone script",
            "dial coaching",
            "cold call script",
        ),
    ),
    (
        DSRAskAction.PITCH_PRACTICE,
        DSRAskCategory.PROSPECT,
        "Pitch Practice",
        "Run a structured pitch rehearsal with a 90-second script, timed drills, "
        "expected pushbacks, and a self-scoring sheet.",
        True,
        False,
        False,
        (
            "pitch practice",
            "practice my pitch",
            "practice pitch",
            "rehearse pitch",
            "pitch drill",
            "elevator pitch",
            "role play",
            "roleplay",
            "pitch me",
        ),
    ),
    (
        DSRAskAction.TOP_PROSPECT_ACCOUNTS,
        DSRAskCategory.PROSPECT,
        "Top Prospect Accounts",
        "Rank the supplied accounts by an explainable prospecting score built from "
        "intent, profile fit, buying stage, and target tier.",
        False,
        True,
        False,
        (
            "top prospect accounts",
            "top prospects",
            "prospect list",
            "account prioritization",
            "prioritize accounts",
            "which accounts should i prospect",
            "who should i call",
            "hot accounts",
            "top accounts",
            "best accounts to work",
        ),
    ),
    (
        DSRAskAction.INTEL_ANALYSIS,
        DSRAskCategory.PROSPECT,
        "Intel Analysis",
        "Analyze technographic and intent intelligence for an account, including "
        "installed vendors, security staffing, and committee coverage.",
        True,
        False,
        False,
        (
            "intel analysis",
            "intelligence analysis",
            "account intel",
            "analyze intel",
            "technographic",
            "technographics",
            "tech stack",
            "installed technologies",
            "install base analysis",
            "signal analysis",
        ),
    ),
    (
        DSRAskAction.MESSAGING,
        DSRAskCategory.PROSPECT,
        "Messaging",
        "Draft persona-specific email, call, and LinkedIn copy anchored to recorded "
        "intent topics and the installed vendor footprint.",
        True,
        False,
        False,
        (
            "messaging",
            "value messaging",
            "outreach message",
            "linkedin message",
            "write an email",
            "draft an email",
            "email copy",
            "sequence copy",
            "write copy",
            "message copy",
        ),
    ),
    (
        DSRAskAction.TERRITORY_WHITESPACE,
        DSRAskCategory.PROSPECT,
        "Territory Whitespace",
        "Map installed-vendor footprint and engagement gaps across a territory to "
        "expose uncovered accounts and displacement whitespace.",
        False,
        True,
        False,
        (
            "territory whitespace",
            "whitespace",
            "white space",
            "territory coverage",
            "territory analysis",
            "territory review",
            "territory plan",
            "coverage gaps",
            "uncovered accounts",
        ),
    ),
    (
        DSRAskAction.TOP_UPSELL_TARGET,
        DSRAskCategory.PROSPECT,
        "Top Upsell, Cross-Sell, and True-Up Target",
        "Rank existing-footprint accounts by expansion potential and label the "
        "recommended motion as upsell, cross-sell, or true-up.",
        False,
        True,
        True,
        (
            "top upsell target",
            "top upsell",
            "upsell target",
            "best upsell",
            "upsell",
            "cross sell",
            "crosssell",
            "true up",
            "trueup",
            "expansion target",
            "expansion opportunity",
            "growth target",
        ),
    ),
    (
        DSRAskAction.ACCOUNT_360_HEALTHCHECK,
        DSRAskCategory.PLAN,
        "Account 360 Healthcheck",
        "Score account health across engagement, committee coverage, value case, "
        "pipeline, intent, and signal coverage.",
        True,
        False,
        False,
        (
            "account 360 healthcheck",
            "account 360",
            "account360",
            "360 healthcheck",
            "account health",
            "healthcheck",
            "health check",
            "account snapshot",
            "account overview",
            "account summary",
            "how is this account doing",
        ),
    ),
    (
        DSRAskAction.ACCOUNT_PLAN,
        DSRAskCategory.PLAN,
        "Account Plan",
        "Build a strategic account plan with footprint, committee map, competitive "
        "landscape, milestones, and a 30/60/90 sequence.",
        True,
        False,
        True,
        (
            "account plan",
            "strategic account plan",
            "build an account plan",
            "account planning",
            "account strategy",
        ),
    ),
    (
        DSRAskAction.DISCOVERY_PREP,
        DSRAskCategory.ENGAGE,
        "Discovery Prep",
        "Prepare a discovery call with an agenda, hypotheses, a question bank from "
        "approved trap questions, attendees, and landmines to avoid.",
        True,
        False,
        False,
        (
            "discovery prep",
            "prepare for discovery",
            "discovery call prep",
            "discovery questions",
            "discovery brief",
            "first call prep",
            "meeting prep",
            "prepare for the meeting",
            "prep for my call",
            "prep me for discovery",
            "discovery",
        ),
    ),
    (
        DSRAskAction.POST_MEETING_NOTES,
        DSRAskCategory.ENGAGE,
        "Post-Meeting Notes and Recap Email",
        "Produce a structured meeting record plus a ready-to-send recap email built "
        "from the facts already on the account record.",
        True,
        False,
        False,
        (
            "post meeting notes",
            "post meeting email",
            "post meeting",
            "meeting notes",
            "meeting recap",
            "meeting summary",
            "summarize the meeting",
            "recap email",
            "call notes",
            "write up my notes",
        ),
    ),
    (
        DSRAskAction.SUGGESTED_FOLLOW_UP,
        DSRAskCategory.ENGAGE,
        "Suggested Follow-Up",
        "Recommend the next best actions with owners and timing derived from stage "
        "age, committee size, value-case status, and intent.",
        True,
        False,
        False,
        (
            "suggested follow up",
            "recommended follow up",
            "follow up",
            "next best action",
            "next action",
            "next steps",
            "what should i do next",
        ),
    ),
    (
        DSRAskAction.DIGITAL_SALES_ROOM,
        DSRAskCategory.ENGAGE,
        "Digital Sales Room Setup",
        "Configure a shared digital sales room: naming, access list, content shelf, "
        "mutual action plan, and engagement signals to watch.",
        True,
        False,
        True,
        (
            "digital sales room",
            "sales room",
            "deal room",
            "dsr setup",
            "set up a dsr",
            "shared room",
            "customer portal",
            "dsr",
        ),
    ),
    (
        DSRAskAction.DMU_EXPANSION,
        DSRAskCategory.PLAN,
        "DMU Expansion",
        "Expand the decision-making unit by comparing engaged stakeholders with the "
        "known contact roster and naming the roles still missing.",
        True,
        False,
        False,
        (
            "dmu expansion",
            "decision making unit",
            "buying committee",
            "buying group",
            "stakeholder map",
            "expand stakeholders",
            "multithreading",
            "multi thread",
            "multithread",
            "single threaded",
            "dmu",
        ),
    ),
    (
        DSRAskAction.OPPORTUNITY_PLAN,
        DSRAskCategory.PLAN,
        "Opportunity Plan",
        "Assemble a qualification and close plan across metrics, economic buyer, "
        "decision criteria, competition, champion, and paper process.",
        True,
        False,
        True,
        (
            "opportunity plan",
            "opportunity planning",
            "deal plan",
            "deal strategy",
            "close plan",
            "meddicc",
            "meddpicc",
        ),
    ),
    (
        DSRAskAction.BUSINESS_VALUE_ASSESSMENT,
        DSRAskCategory.PLAN,
        "Business Value Assessment",
        "Scaffold the business value assessment: scope, value drivers, measurement "
        "plan, investment reference, and approval path.",
        True,
        False,
        True,
        (
            "business value assessment",
            "business value analysis",
            "value assessment",
            "business case",
            "value case",
            "roi case",
            "bva",
        ),
    ),
    (
        DSRAskAction.COMPETITIVE_POSITIONING_DECK,
        DSRAskCategory.ENGAGE,
        "Competitive Positioning Deck and Battlecard",
        "Outline a competitive deck and restate the approved battlecard for every "
        "competitor detected in the account footprint.",
        True,
        False,
        False,
        (
            "competitive positioning deck",
            "competitive positioning",
            "positioning deck",
            "competitive deck",
            "competitor deck",
            "competitor comparison",
            "displacement deck",
            "compete deck",
            "how do we beat",
            "battlecard",
            "battle card",
        ),
    ),
    (
        DSRAskAction.INITIAL_QUOTE,
        DSRAskCategory.NEGOTIATE,
        "Initial Quote",
        "Structure a first quote from the recorded open opportunity amount, with "
        "component split, discount band, approvals, and validity.",
        True,
        False,
        True,
        (
            "initial quote",
            "first quote",
            "create a quote",
            "build a quote",
            "draft quote",
            "pricing quote",
            "price quote",
            "quote",
        ),
    ),
    (
        DSRAskAction.PROPOSAL,
        DSRAskCategory.NEGOTIATE,
        "Proposal",
        "Draft a proposal outline with a readiness gate, executive summary, scope, "
        "commercial summary, and signature path.",
        True,
        False,
        True,
        (
            "create a proposal",
            "draft a proposal",
            "proposal outline",
            "proposal",
            "statement of work",
            "sow",
        ),
    ),
    (
        DSRAskAction.DEAL_RISK,
        DSRAskCategory.NEGOTIATE,
        "Deal Risk",
        "Report deal risk from a supplied risk assessment, or derive hygiene "
        "indicators from the account record when none is provided.",
        True,
        False,
        False,
        (
            "deal risk",
            "risk assessment",
            "risk review",
            "deal health",
            "pipeline risk",
            "stalled deal",
            "stale deal",
            "at risk",
            "what could go wrong",
        ),
    ),
    (
        DSRAskAction.QUOTE_DISCOUNT_CHECKER,
        DSRAskCategory.NEGOTIATE,
        "Quote and Discount Checker",
        "Check a requested discount against the qualification-based guardrail and "
        "name the approval required to proceed.",
        True,
        False,
        True,
        (
            "quote discount checker",
            "discount checker",
            "discount check",
            "check my discount",
            "discount approval",
            "discount guardrail",
            "how much discount",
            "approval threshold",
            "quote checker",
            "quote approval",
            "discount",
        ),
    ),
    (
        DSRAskAction.CONTRACT_REVIEW,
        DSRAskCategory.NEGOTIATE,
        "Contract Review",
        "Review contract structure against the account record: entitlement basis, "
        "true-up terms, displacement clauses, and approval routing.",
        True,
        False,
        True,
        (
            "contract review",
            "review the contract",
            "review my contract",
            "contract terms",
            "contract check",
            "terms review",
            "legal review",
            "redlines",
            "redline",
            "msa",
        ),
    ),
    (
        DSRAskAction.POST_SALES_HANDOFF,
        DSRAskCategory.POST_SALE,
        "Post-Sales Handoff",
        "Assemble the handoff packet: account facts, purchased scope, stakeholder "
        "roster, success criteria, onboarding milestones, and open risks.",
        True,
        False,
        True,
        (
            "post sales handoff",
            "customer success handoff",
            "implementation handoff",
            "onboarding handoff",
            "transition to customer success",
            "transition to cs",
            "hand this off",
            "customer success",
            "handoff",
            "hand off",
            "handover",
        ),
    ),
    (
        DSRAskAction.RULES_OF_ENGAGEMENT,
        DSRAskCategory.ENABLEMENT,
        "Rules of Engagement",
        "Explain the demo rules of engagement for account ownership, territory "
        "splits, overlay support, registration, and escalation.",
        False,
        False,
        True,
        (
            "rules of engagement",
            "engagement rules",
            "account ownership rules",
            "who owns this account",
            "territory rules",
            "split rules",
            "opportunity registration",
            "roe",
        ),
    ),
    (
        DSRAskAction.COMMISSION_PLANS,
        DSRAskCategory.ENABLEMENT,
        "Commission Plans",
        "Explain the demo commission structure, expansion credit rules, payout "
        "timing, and an illustrative payout calculation.",
        False,
        False,
        True,
        (
            "commission plans",
            "commission plan",
            "compensation plan",
            "comp plan",
            "how do i get paid",
            "quota credit",
            "accelerator",
            "commission",
            "quota",
            "payout",
            "spiff",
        ),
    ),
    (
        DSRAskAction.PRODUCT_OVERVIEW,
        DSRAskCategory.ENABLEMENT,
        "Product Overview",
        "Summarize the demo product capability areas and map recorded customer "
        "intent topics onto them.",
        False,
        False,
        True,
        (
            "product overview",
            "product portfolio",
            "product capabilities",
            "capabilities overview",
            "platform overview",
            "solution overview",
            "product summary",
            "what do we sell",
        ),
    ),
)

_DEFAULT_ACTION: Final[DSRAskAction] = DSRAskAction.ACCOUNT_360_HEALTHCHECK

_DEMO_NOTE: Final[str] = (
    "> **Local demo guidance.** The process, pricing, policy, and product framing in "
    "this section is bundled sample guidance for this local build. It is not an "
    "approved company policy and contains no customer-supplied facts."
)

# Stage ladder used to explain the ``stage`` codes recorded on accounts. This is a
# local demo convention, not a customer fact.
STAGE_LADDER: Final[tuple[tuple[str, str], ...]] = (
    ("SS10", "Qualify the opportunity and confirm a compelling reason to act"),
    ("SS20", "Validate business value with the economic buyer"),
    ("SS30", "Prove technical fit and confirm the success criteria"),
    ("SS40", "Agree commercial terms and the mutual close plan"),
    ("SS50", "Complete approvals, security review, and paper process"),
    ("SS60", "Closed won and transitioned to delivery"),
)

# Illustrative commercial construction applied to ``open_opportunity_amount``.
_QUOTE_SPLIT: Final[tuple[tuple[str, float, str], ...]] = (
    ("Identity platform subscription", 0.55, "Core platform entitlement for the term"),
    ("Governance and access modules", 0.30, "Certification, request, and reporting scope"),
    ("Onboarding and enablement services", 0.15, "Guided deployment and admin enablement"),
)
_DEMO_TERM_MONTHS: Final[int] = 36

# Demo product framing used by the product overview and messaging actions.
_DEMO_CAPABILITY_AREAS: Final[tuple[tuple[str, str], ...]] = (
    (
        "Identity governance",
        "Certify who has access, why they have it, and whether it is still required.",
    ),
    (
        "Privileged access modernization",
        "Bring high-risk and privileged accounts under the same governance controls.",
    ),
    (
        "Access request and provisioning",
        "Route joiner, mover, and leaver changes through auditable workflows.",
    ),
    (
        "Access intelligence and reporting",
        "Report access risk and produce audit evidence from a single place.",
    ),
)


def _pad(text: str) -> str:
    """Normalize ``text`` and wrap it in spaces so aliases match on word edges."""
    folded = "".join(character if character.isalnum() else " " for character in text.lower())
    return f" {' '.join(folded.split())} "


_CATALOG: Final[tuple[DSRAskCatalogEntry, ...]] = tuple(
    DSRAskCatalogEntry(
        action=action,
        category=category,
        title=title,
        description=description,
        requires_account=requires_account,
        requires_portfolio=requires_portfolio,
        uses_demo_policy=uses_demo_policy,
        aliases=aliases,
    )
    for (
        action,
        category,
        title,
        description,
        requires_account,
        requires_portfolio,
        uses_demo_policy,
        aliases,
    ) in _CATALOG_SPEC
)

_ENTRY_BY_ACTION: Final[dict[DSRAskAction, DSRAskCatalogEntry]] = {
    entry.action: entry for entry in _CATALOG
}

# (padded alias, raw alias, action, declaration order) tuples used by the classifier.
_ALIAS_INDEX: Final[tuple[tuple[str, str, DSRAskAction, int], ...]] = tuple(
    (_pad(alias), alias, entry.action, order)
    for order, entry in enumerate(_CATALOG)
    for alias in entry.aliases
)

_DISCOUNT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:%|percent\b|pct\b)"
)


# ---------------------------------------------------------------------------
# Field readers
# ---------------------------------------------------------------------------


_text = text_value


def _iso(source: Any, *names: str, default: str = "") -> str:
    """Read a date or datetime field and render it in ISO-8601 form."""
    raw = value(source, *names, default=None)
    if raw is None:
        return default
    formatter = getattr(raw, "isoformat", None)
    if callable(formatter):
        return str(formatter())
    rendered = str(raw).strip()
    return rendered or default


_number = number_value
_integer = int_value
_flag = bool_value
_items = items_value
_strings = string_values


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


_money = format_money
_money_compact = format_money_compact


def _cell(text: str) -> str:
    """Escape pipe characters so ``text`` is safe inside a Markdown table cell."""
    return text.replace("|", "\\|")


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Render a GitHub-flavoured Markdown table."""
    lines = [
        "| " + " | ".join(_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(field) for field in row) + " |" for row in rows)
    return lines


def _bullets(items: Iterable[str]) -> list[str]:
    """Render ``items`` as a Markdown bullet list."""
    return [f"- {item}" for item in items]


def _numbered(items: Iterable[str]) -> list[str]:
    """Render ``items`` as a Markdown ordered list."""
    return [f"{index}. {item}" for index, item in enumerate(items, start=1)]


def _joined(items: Sequence[str], empty: str) -> str:
    """Join ``items`` with commas, returning ``empty`` when there is nothing to join."""
    return ", ".join(items) if items else empty


def _unavailable(label: str) -> str:
    """Render a consistent italic note for data missing from the local dataset."""
    return f"_No {label} is present in the local dataset for this account._"


def stage_rank(stage: str) -> int:
    """Return the numeric portion of a sales stage code, or ``0`` when absent."""
    digits = "".join(character for character in stage if character.isdigit())
    return int(digits) if digits else 0


def stage_objective(stage: str) -> str:
    """Return the demo ladder objective for ``stage``."""
    rank = stage_rank(stage)
    for code, objective in STAGE_LADDER:
        if stage_rank(code) == rank and rank:
            return objective
    return "Stage is not recorded on the account; confirm qualification before forecasting"


def next_stage(stage: str) -> tuple[str, str]:
    """Return the next demo ladder stage and its objective after ``stage``."""
    rank = stage_rank(stage)
    for code, objective in STAGE_LADDER:
        if stage_rank(code) > rank:
            return code, objective
    return STAGE_LADDER[-1]


_stage_rank = stage_rank
_stage_objective = stage_objective
_next_stage = next_stage


def _normalize_vendor(name: str) -> str:
    """Reduce a vendor or product name to comparable alphanumeric characters."""
    return "".join(character for character in name.lower() if character.isalnum())


# ---------------------------------------------------------------------------
# Extracted record facts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AccountFacts:
    """Canonical Salesforce account fields, read once through :func:`value`."""

    name: str
    account_id: str
    domain: str
    industry: str
    annual_revenue: float
    employee_count: int
    owner_id: str
    territory: str
    target_tier: str
    stage: str
    last_activity_date: str
    bva_complete: bool
    days_in_stage: int
    stakeholder_count: int
    current_products: tuple[str, ...]
    open_opportunity_amount: float

    @classmethod
    def from_object(cls, account: Any) -> _AccountFacts:
        """Extract account facts from a model, mapping, or test double."""
        return cls(
            name=_text(account, "name", "account_name", default="Unnamed account"),
            account_id=_text(account, "id", "account_id", default="unknown-id"),
            domain=_text(account, "domain", default="unknown-domain"),
            industry=_text(account, "industry", default="Industry not recorded"),
            annual_revenue=_number(account, "annual_revenue"),
            employee_count=_integer(account, "employee_count"),
            owner_id=_text(account, "owner_id", "account_owner", default="unassigned"),
            territory=_text(account, "territory", default="Territory not recorded"),
            target_tier=_text(account, "target_tier", default="Tier not recorded"),
            stage=_text(account, "stage", default=""),
            last_activity_date=_iso(account, "last_activity_date", default="not recorded"),
            bva_complete=_flag(account, "bva_complete"),
            days_in_stage=_integer(account, "days_in_stage"),
            stakeholder_count=_integer(account, "stakeholder_count"),
            current_products=_strings(account, "current_products"),
            open_opportunity_amount=_number(account, "open_opportunity_amount"),
        )

    @property
    def stage_display(self) -> str:
        """Return the stage code or an explicit "not recorded" marker."""
        return self.stage or "not recorded"

    @property
    def revenue_display(self) -> str:
        """Return compact annual revenue for headline lines."""
        return _money_compact(self.annual_revenue)

    @property
    def products_display(self) -> str:
        """Return the installed product footprint as recorded on the account."""
        return _joined(self.current_products, "no products recorded")


@dataclass(frozen=True)
class _IntentFacts:
    """Canonical intent-signal fields."""

    domain: str
    buying_stage: str
    intent_score: int
    intent_topics: tuple[str, ...]
    profile_fit: str
    observed_at: str
    source: str

    @classmethod
    def from_object(cls, signal: Any) -> _IntentFacts:
        """Extract intent facts from a model, mapping, or test double."""
        return cls(
            domain=_text(signal, "domain", default="unknown-domain"),
            buying_stage=_text(signal, "buying_stage", default="not recorded"),
            intent_score=_integer(signal, "intent_score", "score"),
            intent_topics=_strings(signal, "intent_topics"),
            profile_fit=_text(signal, "profile_fit", default="not recorded"),
            observed_at=_iso(signal, "observed_at", default="not recorded"),
            source=_text(signal, "source", default="local intent source"),
        )

    @property
    def topics_display(self) -> str:
        """Return recorded intent topics as a comma-separated string."""
        return _joined(self.intent_topics, "no topics recorded")

    @property
    def lead_topic(self) -> str:
        """Return the highest-order recorded intent topic."""
        return self.intent_topics[0] if self.intent_topics else "identity security"


@dataclass(frozen=True)
class _ContactFacts:
    """Canonical buying-committee contact fields."""

    name: str
    title: str
    email: str
    seniority: str
    department: str
    linkedin_url: str
    location: str

    @classmethod
    def from_object(cls, contact: Any) -> _ContactFacts:
        """Extract contact facts from a model, mapping, or test double."""
        return cls(
            name=_text(contact, "name", "full_name", default="Unnamed contact"),
            title=_text(contact, "title", default="Title not recorded"),
            email=_text(contact, "email", default="email not recorded"),
            seniority=_text(contact, "seniority", default="Seniority not recorded"),
            department=_text(contact, "department", default="Department not recorded"),
            linkedin_url=_text(contact, "linkedin_url", default=""),
            location=_text(contact, "location", default=""),
        )

    @property
    def rank(self) -> int:
        """Return a deterministic persona tier, where ``0`` is most senior."""
        haystack = f"{self.seniority} {self.title}".lower()
        if "c-level" in haystack or "chief" in haystack or "ciso" in haystack:
            return 0
        if "vice president" in haystack or "vp" in haystack:
            return 1
        if "director" in haystack:
            return 2
        if "head" in haystack or "manager" in haystack:
            return 3
        return 4

    @property
    def rank_label(self) -> str:
        """Describe why this contact sits in its persona tier."""
        return {
            0: "Executive sponsor candidate",
            1: "Senior program owner",
            2: "Program and evaluation lead",
            3: "Operational owner",
            4: "Adjacent stakeholder",
        }[self.rank]

    @property
    def first_name(self) -> str:
        """Return the contact's first name as recorded."""
        return self.name.split()[0] if self.name.split() else self.name


@dataclass(frozen=True)
class _IntelFacts:
    """Canonical technographic fields plus a persona-ordered contact roster."""

    domain: str
    installed_technologies: tuple[str, ...]
    it_security_headcount: int
    contacts: tuple[_ContactFacts, ...]
    last_verified_at: str
    source: str

    @classmethod
    def from_object(cls, intel: Any) -> _IntelFacts:
        """Extract technographic facts from a model, mapping, or test double."""
        contacts = tuple(
            _ContactFacts.from_object(contact)
            for contact in _items(intel, "key_contacts", "contacts")
        )
        return cls(
            domain=_text(intel, "domain", default="unknown-domain"),
            installed_technologies=_strings(
                intel, "installed_technologies", "technologies"
            ),
            it_security_headcount=_integer(intel, "it_security_headcount"),
            contacts=tuple(sorted(contacts, key=lambda item: (item.rank, item.name))),
            last_verified_at=_iso(intel, "last_verified_at", default="not recorded"),
            source=_text(intel, "source", default="local technographic source"),
        )

    @property
    def technologies_display(self) -> str:
        """Return the installed technology list as a comma-separated string."""
        return _joined(self.installed_technologies, "no technologies recorded")

    @property
    def departments(self) -> tuple[str, ...]:
        """Return the distinct departments represented in the contact roster."""
        return tuple(dict.fromkeys(contact.department for contact in self.contacts))


@dataclass(frozen=True)
class _CardFacts:
    """Canonical battlecard fields."""

    competitor_name: str
    weaknesses: tuple[str, ...]
    kill_points: str
    trap_questions: tuple[str, ...]
    value_hook: str
    source: str

    @classmethod
    def from_object(cls, card: Any) -> _CardFacts:
        """Extract battlecard facts from a model, mapping, or test double."""
        return cls(
            competitor_name=_text(
                card, "competitor_name", "competitor", default="Unnamed competitor"
            ),
            weaknesses=_strings(card, "weaknesses"),
            kill_points=_text(card, "kill_points", default=""),
            trap_questions=_strings(card, "trap_questions"),
            value_hook=_text(card, "value_hook", default=""),
            source=_text(card, "source", default="Local battlecard"),
        )

    def matches(self, vendor: str) -> bool:
        """Report whether this card covers ``vendor`` using normalized name matching."""
        left = _normalize_vendor(vendor)
        right = _normalize_vendor(self.competitor_name)
        return bool(left and right and (left in right or right in left))


@dataclass(frozen=True)
class _RiskFacts:
    """Fields read from a caller-supplied deal-risk assessment."""

    risk_level: str
    risk_score: int
    summary: str
    flags: tuple[tuple[str, str, str, str], ...]

    @classmethod
    def from_object(cls, risk: Any) -> _RiskFacts:
        """Extract risk facts from a ``DealRiskResult``, mapping, or test double."""
        flags: list[tuple[str, str, str, str]] = []
        for flag in _items(risk, "flags"):
            flags.append(
                (
                    _text(flag, "code", default="unspecified").replace("_", " ").title(),
                    _text(flag, "severity", default="unspecified").title(),
                    _text(flag, "evidence", default="No evidence recorded."),
                    _text(flag, "recommendation", default="No recommendation recorded."),
                )
            )
        return cls(
            risk_level=_text(risk, "risk_level", default="not recorded").title(),
            risk_score=_integer(risk, "risk_score"),
            summary=_text(risk, "summary", default="No risk summary was supplied."),
            flags=tuple(flags),
        )


@dataclass(frozen=True)
class _DealEconomics:
    """Commercial values derived from the account's recorded opportunity fields."""

    open_amount: float
    stage: str
    stage_rank: int
    bva_complete: bool
    stakeholder_count: int
    components: tuple[tuple[str, float, str], ...]
    approved_discount_pct: int
    floor_amount: float
    approval_owner: str
    qualification_label: str
    term_months: int

    @classmethod
    def from_account(cls, account: _AccountFacts) -> _DealEconomics:
        """Derive the commercial construction used by quoting and paper actions."""
        amount = account.open_opportunity_amount
        components: list[tuple[str, float, str]] = []
        allocated = 0.0
        for index, (label, share, note) in enumerate(_QUOTE_SPLIT):
            if index == len(_QUOTE_SPLIT) - 1:
                component = round(amount - allocated, 2)
            else:
                component = round(amount * share, 2)
                allocated += component
            components.append((label, component, note))

        rank = _stage_rank(account.stage)
        discount = 8
        if account.bva_complete:
            discount += 4
        if account.stakeholder_count >= 3:
            discount += 3
        if rank >= 40:
            discount += 2
        discount = min(discount, 17)

        if amount >= 1_000_000:
            approval_owner = "Deal desk plus region vice president"
        elif amount >= 750_000:
            approval_owner = "Region vice president"
        elif amount >= 250_000:
            approval_owner = "Area vice president"
        else:
            approval_owner = "Regional sales manager"

        if account.bva_complete and account.stakeholder_count >= 3:
            qualification = "Committee-validated"
        elif account.bva_complete or account.stakeholder_count >= 2:
            qualification = "Partially validated"
        else:
            qualification = "Single-threaded"

        return cls(
            open_amount=amount,
            stage=account.stage_display,
            stage_rank=rank,
            bva_complete=account.bva_complete,
            stakeholder_count=account.stakeholder_count,
            components=tuple(components),
            approved_discount_pct=discount,
            floor_amount=round(amount * (1 - discount / 100), 2),
            approval_owner=approval_owner,
            qualification_label=qualification,
            term_months=_DEMO_TERM_MONTHS,
        )

    @property
    def annualized_amount(self) -> float:
        """Return the term amount spread evenly across twelve-month periods."""
        years = self.term_months / 12
        return round(self.open_amount / years, 2) if years else self.open_amount


@dataclass(frozen=True)
class _ScoredAccount:
    """An account paired with a derived score, band, and explanation."""

    account: _AccountFacts
    intent: _IntentFacts | None
    score: int
    band: str
    reasons: tuple[str, ...]
    motion: str


@dataclass(frozen=True)
class _AskContext:
    """Everything a renderer may read, extracted once for determinism."""

    entry: DSRAskCatalogEntry
    message: str
    account: _AccountFacts | None
    accounts: tuple[_AccountFacts, ...]
    intent: _IntentFacts | None
    signals: Mapping[str, _IntentFacts]
    intel: _IntelFacts | None
    cards: tuple[_CardFacts, ...]
    risk: _RiskFacts | None
    economics: _DealEconomics | None
    vendors: tuple[str, ...]
    matched_cards: tuple[tuple[str, _CardFacts], ...]
    unmatched_vendors: tuple[str, ...]
    requested_discount_pct: float | None

    @property
    def named_account(self) -> _AccountFacts:
        """Return the focus account, which renderers only reach when present."""
        if self.account is None:  # pragma: no cover - guarded by the run() gate
            raise ValueError("This action requires an account")
        return self.account

    @property
    def named_economics(self) -> _DealEconomics:
        """Return derived economics, which exist whenever an account exists."""
        if self.economics is None:  # pragma: no cover - guarded by the run() gate
            raise ValueError("This action requires an account")
        return self.economics

    def intent_for(self, account: _AccountFacts) -> _IntentFacts | None:
        """Return the intent signal recorded for ``account``'s domain, if any."""
        return self.signals.get(account.domain)

    @property
    def primary_contact(self) -> _ContactFacts | None:
        """Return the most senior known contact, if a roster was supplied."""
        if self.intel is None or not self.intel.contacts:
            return None
        return self.intel.contacts[0]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class DSRAskCatalogAgent(BaseAgent[DSRAskResult]):
    """Answer any of the twenty-six Ask catalog requests from local records only.

    The agent is intentionally free of external dependencies: it classifies a seller
    request against a fixed alias table, then renders Markdown from the canonical
    records the caller supplies. Callers pass records as ``Any`` -- Pydantic models,
    mappings, or test doubles all work -- and every field is read through
    :func:`henry_dsr_agent.agents.base.value`.

    Example::

        agent = DSRAskCatalogAgent()
        result = await agent.run("check a 22% discount", account=account)
        assert result.action is DSRAskAction.QUOTE_DISCOUNT_CHECKER
    """

    def __init__(self, **kwargs: Any) -> None:
        """Build the renderer table and verify that every action is implemented."""
        super().__init__(**kwargs)
        self._renderers: dict[DSRAskAction, Callable[[_AskContext], list[str]]] = {
            DSRAskAction.COLD_CALL_COACHING: self._render_cold_call_coaching,
            DSRAskAction.PITCH_PRACTICE: self._render_pitch_practice,
            DSRAskAction.TOP_PROSPECT_ACCOUNTS: self._render_top_prospect_accounts,
            DSRAskAction.INTEL_ANALYSIS: self._render_intel_analysis,
            DSRAskAction.MESSAGING: self._render_messaging,
            DSRAskAction.TERRITORY_WHITESPACE: self._render_territory_whitespace,
            DSRAskAction.TOP_UPSELL_TARGET: self._render_top_upsell_target,
            DSRAskAction.ACCOUNT_360_HEALTHCHECK: self._render_account_360_healthcheck,
            DSRAskAction.ACCOUNT_PLAN: self._render_account_plan,
            DSRAskAction.DISCOVERY_PREP: self._render_discovery_prep,
            DSRAskAction.POST_MEETING_NOTES: self._render_post_meeting_notes,
            DSRAskAction.SUGGESTED_FOLLOW_UP: self._render_suggested_follow_up,
            DSRAskAction.DIGITAL_SALES_ROOM: self._render_digital_sales_room,
            DSRAskAction.DMU_EXPANSION: self._render_dmu_expansion,
            DSRAskAction.OPPORTUNITY_PLAN: self._render_opportunity_plan,
            DSRAskAction.BUSINESS_VALUE_ASSESSMENT: self._render_business_value_assessment,
            DSRAskAction.COMPETITIVE_POSITIONING_DECK: self._render_positioning_deck,
            DSRAskAction.INITIAL_QUOTE: self._render_initial_quote,
            DSRAskAction.PROPOSAL: self._render_proposal,
            DSRAskAction.DEAL_RISK: self._render_deal_risk,
            DSRAskAction.QUOTE_DISCOUNT_CHECKER: self._render_quote_discount_checker,
            DSRAskAction.CONTRACT_REVIEW: self._render_contract_review,
            DSRAskAction.POST_SALES_HANDOFF: self._render_post_sales_handoff,
            DSRAskAction.RULES_OF_ENGAGEMENT: self._render_rules_of_engagement,
            DSRAskAction.COMMISSION_PLANS: self._render_commission_plans,
            DSRAskAction.PRODUCT_OVERVIEW: self._render_product_overview,
        }
        missing = [action.value for action in DSRAskAction if action not in self._renderers]
        if missing:  # pragma: no cover - guards future catalog edits
            raise RuntimeError(f"Ask catalog actions without renderers: {', '.join(missing)}")

    # -- Catalog metadata ---------------------------------------------------

    @staticmethod
    def catalog() -> tuple[DSRAskCatalogEntry, ...]:
        """Return metadata for every supported action, in presentation order."""
        return _CATALOG

    @staticmethod
    def entry(action: DSRAskAction | str) -> DSRAskCatalogEntry:
        """Return the catalog entry for ``action``, accepting an enum or string."""
        return _ENTRY_BY_ACTION[DSRAskCatalogAgent.resolve_action(action)]

    @staticmethod
    def categories() -> tuple[DSRAskCategory, ...]:
        """Return the distinct categories present in the catalog, in order."""
        return tuple(dict.fromkeys(item.category for item in _CATALOG))

    @classmethod
    def catalog_markdown(cls) -> str:
        """Render the full catalog as Markdown grouped by category."""
        lines = ["# Ask Henry Catalog", ""]
        lines.append(f"{len(_CATALOG)} actions across {len(cls.categories())} categories.")
        for category in cls.categories():
            entries = [item for item in _CATALOG if item.category is category]
            lines += ["", f"## {category.value.replace('_', ' ').title()}", ""]
            lines += _table(
                ("Action", "What it does", "Needs an account", "Needs a portfolio"),
                [
                    (
                        f"`{item.action.value}` — {item.title}",
                        item.description,
                        "Yes" if item.requires_account else "No",
                        "Yes" if item.requires_portfolio else "No",
                    )
                    for item in entries
                ],
            )
        return "\n".join(lines)

    @staticmethod
    def resolve_action(action: DSRAskAction | str) -> DSRAskAction:
        """Coerce an enum, value, or member name into a :class:`DSRAskAction`.

        Raises:
            ValueError: If ``action`` does not name a supported catalog action.
        """
        if isinstance(action, DSRAskAction):
            return action
        candidate = _pad(str(action)).strip().replace(" ", "_")
        for member in DSRAskAction:
            if candidate in {member.value, member.name.lower()}:
                return member
        raise ValueError(f"Unknown Ask catalog action: {action!r}")

    # -- Classification -----------------------------------------------------

    def classify(
        self,
        message: str,
        requested_action: DSRAskAction | str | None = None,
    ) -> DSRAskClassification:
        """Map a free-text request onto a catalog action, deterministically.

        An explicit ``requested_action`` always wins. Otherwise the longest matching
        alias wins, with catalog declaration order breaking ties, so that specific
        phrases such as ``"post meeting email"`` outrank generic ones such as
        ``"write an email"``. When nothing matches, the catalog default is returned
        and ``source`` is ``"default"``.

        Args:
            message: The seller's request text. May be empty.
            requested_action: An explicit action chosen in the UI, if any.

        Returns:
            A :class:`DSRAskClassification` carrying the action, the alias that
            matched, a confidence value, and the runner-up actions.
        """
        if requested_action is not None:
            action = self.resolve_action(requested_action)
            return DSRAskClassification(
                action=action,
                category=_ENTRY_BY_ACTION[action].category,
                source="requested",
                matched_alias=None,
                confidence=1.0,
                alternatives=(),
            )

        normalized = _pad(message)
        candidates = sorted(
            (-len(padded), order, raw, action)
            for padded, raw, action, order in _ALIAS_INDEX
            if padded in normalized
        )
        if not candidates:
            return DSRAskClassification(
                action=_DEFAULT_ACTION,
                category=_ENTRY_BY_ACTION[_DEFAULT_ACTION].category,
                source="default",
                matched_alias=None,
                confidence=0.0,
                alternatives=(),
            )

        _, _, matched_alias, action = candidates[0]
        alternatives = tuple(
            item
            for item in dict.fromkeys(candidate[3] for candidate in candidates)
            if item is not action
        )[:3]
        return DSRAskClassification(
            action=action,
            category=_ENTRY_BY_ACTION[action].category,
            source="alias",
            matched_alias=matched_alias,
            confidence=round(min(1.0, 0.5 + len(matched_alias) / 48), 2),
            alternatives=alternatives,
        )

    def classify_action(
        self,
        message: str,
        requested_action: DSRAskAction | str | None = None,
    ) -> DSRAskAction:
        """Return only the action selected by :meth:`classify`."""
        return self.classify(message, requested_action).action

    # -- Execution ----------------------------------------------------------

    async def run(
        self,
        message: str = "",
        *,
        requested_action: DSRAskAction | str | None = None,
        account: Any | None = None,
        accounts: Sequence[Any] | None = None,
        intent: Any | None = None,
        signals: Sequence[Any] | None = None,
        technographics: Any | None = None,
        battlecards: Sequence[Any] | None = None,
        deal_risk: Any | None = None,
        requested_discount_pct: float | None = None,
        **_: Any,
    ) -> DSRAskResult:
        """Classify ``message`` and render the matching catalog action.

        Args:
            message: The seller's free-text request.
            requested_action: Explicit action override from a menu selection.
            account: Focus account record (``SalesforceAccount``-shaped).
            accounts: Portfolio of account records for ranking actions.
            intent: Intent signal for the focus account.
            signals: Intent signals for the portfolio, indexed here by ``domain``.
            technographics: Technographic record for the focus account.
            battlecards: Approved battlecards available for matching.
            deal_risk: A previously computed deal-risk assessment.
            requested_discount_pct: Discount to validate; parsed from ``message``
                when omitted.

        Returns:
            A :class:`DSRAskResult`. When an action needs an account or a portfolio
            that was not supplied, the result is a helpful selection prompt with
            ``needs_account_selection`` set rather than an exception.
        """
        classification = self.classify(message, requested_action)
        entry = _ENTRY_BY_ACTION[classification.action]

        account_facts = _AccountFacts.from_object(account) if account is not None else None
        portfolio = tuple(_AccountFacts.from_object(item) for item in (accounts or ()))
        if not portfolio and account_facts is not None:
            portfolio = (account_facts,)

        signal_facts = [_IntentFacts.from_object(item) for item in (signals or ()) if item]
        if intent is not None:
            signal_facts.append(_IntentFacts.from_object(intent))
        signal_index = {item.domain: item for item in signal_facts}
        intent_facts = _IntentFacts.from_object(intent) if intent is not None else None
        if intent_facts is None and account_facts is not None:
            intent_facts = signal_index.get(account_facts.domain)

        intel_facts = (
            _IntelFacts.from_object(technographics) if technographics is not None else None
        )
        card_facts = tuple(_CardFacts.from_object(item) for item in (battlecards or ()) if item)
        risk_facts = _RiskFacts.from_object(deal_risk) if deal_risk is not None else None

        vendors: tuple[str, ...] = ()
        if account_facts is not None or intel_facts is not None:
            merged = list(account_facts.current_products) if account_facts else []
            merged += list(intel_facts.installed_technologies) if intel_facts else []
            vendors = tuple(dict.fromkeys(merged))

        matched: list[tuple[str, _CardFacts]] = []
        unmatched: list[str] = []
        for vendor in vendors:
            card = next((item for item in card_facts if item.matches(vendor)), None)
            if card is None:
                unmatched.append(vendor)
            else:
                matched.append((vendor, card))

        context = _AskContext(
            entry=entry,
            message=message,
            account=account_facts,
            accounts=portfolio,
            intent=intent_facts,
            signals=signal_index,
            intel=intel_facts,
            cards=card_facts,
            risk=risk_facts,
            economics=(
                _DealEconomics.from_account(account_facts) if account_facts else None
            ),
            vendors=vendors,
            matched_cards=tuple(matched),
            unmatched_vendors=tuple(unmatched),
            requested_discount_pct=(
                requested_discount_pct
                if requested_discount_pct is not None
                else self._parse_discount(message)
            ),
        )

        if entry.requires_account and context.account is None:
            return self._selection_prompt(entry, classification, context, needs_single=True)
        if entry.requires_portfolio and not context.accounts:
            return self._selection_prompt(entry, classification, context, needs_single=False)

        body = self._renderers[classification.action](context)
        title = entry.title
        if context.account is not None and entry.requires_account:
            title = f"{entry.title} — {context.account.name}"
        return DSRAskResult(
            action=classification.action,
            category=entry.category,
            title=title,
            markdown="\n".join([f"# {title}", "", *body]).rstrip() + "\n",
            requires_account=entry.requires_account,
            account_name=context.account.name if context.account else None,
            needs_account_selection=False,
            data_sources=self._data_sources(entry, context),
            classification=classification,
        )

    # -- Input helpers ------------------------------------------------------

    @staticmethod
    def _parse_discount(message: str) -> float | None:
        """Extract the first percentage mentioned in ``message``, if any."""
        match = _DISCOUNT_PATTERN.search(message)
        if match is None:
            return None
        try:
            parsed = float(match.group(1))
        except ValueError:  # pragma: no cover - pattern guarantees a float
            return None
        return parsed if 0 <= parsed <= 100 else None

    @staticmethod
    def _data_sources(entry: DSRAskCatalogEntry, context: _AskContext) -> tuple[str, ...]:
        """List the record types that contributed to a rendered answer."""
        sources: list[str] = []
        if context.account is not None or context.accounts:
            sources.append("Salesforce accounts")
        if context.intent is not None or context.signals:
            source = next(
                (item.source for item in context.signals.values() if item.source),
                "intent signals",
            )
            sources.append(f"Intent signals ({source})")
        if context.intel is not None:
            sources.append(f"Technographics ({context.intel.source})")
        if context.cards:
            sources.append("Approved battlecards")
        if context.risk is not None:
            sources.append("Deal-risk assessment")
        if entry.uses_demo_policy:
            sources.append("Local demo guidance")
        return tuple(dict.fromkeys(sources))

    def _selection_prompt(
        self,
        entry: DSRAskCatalogEntry,
        classification: DSRAskClassification,
        context: _AskContext,
        *,
        needs_single: bool,
    ) -> DSRAskResult:
        """Return a helpful selection prompt instead of raising on missing input."""
        subject = "an account" if needs_single else "a set of accounts"
        title = f"Select {subject} for: {entry.title}"
        lines = [
            f"**{entry.title}** needs {subject} before it can be answered.",
            "",
            f"_{entry.description}_",
            "",
            "## What to send",
            "",
        ]
        if needs_single:
            lines += _bullets(
                (
                    "`account` — the Salesforce account record to focus on, or an "
                    "`account_id` the caller can resolve to one.",
                    "`intent` — the matching intent signal, so buying stage and topics "
                    "can be quoted exactly.",
                    "`technographics` — the matching technographic record, so the "
                    "installed vendors and contact roster can be quoted exactly.",
                    "`battlecards` — approved cards, so competitor guidance is not "
                    "improvised.",
                )
            )
        else:
            lines += _bullets(
                (
                    "`accounts` — the account records to compare, typically one "
                    "territory at a time.",
                    "`signals` — the intent signals for those accounts, matched on "
                    "`domain`.",
                )
            )
        if context.accounts:
            lines += ["", "## Accounts available in this session", ""]
            lines += _table(
                ("Account", "Account ID", "Territory", "Tier", "Stage"),
                [
                    (
                        item.name,
                        item.account_id,
                        item.territory,
                        item.target_tier,
                        item.stage_display,
                    )
                    for item in context.accounts
                ],
            )
            lines += ["", "Reply with one of the account names above to continue."]
        else:
            lines += [
                "",
                "No account records were supplied with this request, so there is "
                "nothing to list. Load accounts by territory first, then ask again.",
            ]
        if classification.alternatives:
            lines += [
                "",
                "## Did you mean something else?",
                "",
                *_bullets(
                    f"`{item.value}` — {_ENTRY_BY_ACTION[item].title}"
                    for item in classification.alternatives
                ),
            ]
        return DSRAskResult(
            action=classification.action,
            category=entry.category,
            title=title,
            markdown="\n".join([f"# {title}", "", *lines]).rstrip() + "\n",
            requires_account=entry.requires_account,
            account_name=None,
            needs_account_selection=True,
            data_sources=self._data_sources(entry, context),
            classification=classification,
        )

    # -- Shared sections ----------------------------------------------------

    @staticmethod
    def _account_snapshot(account: _AccountFacts) -> list[str]:
        """Render every recorded account field as a two-column table."""
        return [
            "## Account Record",
            "",
            *_table(
                ("Field", "Value"),
                [
                    ("Account", f"{account.name} (`{account.account_id}`)"),
                    ("Domain", account.domain),
                    ("Industry", account.industry),
                    (
                        "Annual revenue",
                        f"{_money(account.annual_revenue)} ({account.revenue_display})",
                    ),
                    ("Employees", f"{account.employee_count:,}"),
                    ("Owner", account.owner_id),
                    ("Territory", account.territory),
                    ("Target tier", account.target_tier),
                    ("Stage", account.stage_display),
                    ("Days in stage", str(account.days_in_stage)),
                    ("Last activity", account.last_activity_date),
                    ("BVA complete", "Yes" if account.bva_complete else "No"),
                    ("Engaged stakeholders", str(account.stakeholder_count)),
                    ("Current products", account.products_display),
                    ("Open opportunity", _money(account.open_opportunity_amount)),
                ],
            ),
        ]

    @staticmethod
    def _intent_section(intent: _IntentFacts | None) -> list[str]:
        """Render every recorded intent-signal field, or an explicit gap note."""
        lines = ["## Intent Signal", ""]
        if intent is None:
            return [*lines, _unavailable("intent signal")]
        lines += _table(
            ("Field", "Value"),
            [
                ("Domain", intent.domain),
                ("Buying stage", intent.buying_stage),
                ("Intent score", f"{intent.intent_score}/100"),
                ("Profile fit", intent.profile_fit),
                ("Topics", intent.topics_display),
                ("Observed at", intent.observed_at),
                ("Source", intent.source),
            ],
        )
        return lines

    @staticmethod
    def _intel_section(intel: _IntelFacts | None) -> list[str]:
        """Render technographic fields and the persona-ordered contact roster."""
        lines = ["## Technographics and Contacts", ""]
        if intel is None:
            return [*lines, _unavailable("technographic record")]
        lines += _table(
            ("Field", "Value"),
            [
                ("Domain", intel.domain),
                ("Installed technologies", intel.technologies_display),
                ("IT security headcount", f"{intel.it_security_headcount:,}"),
                ("Known contacts", str(len(intel.contacts))),
                ("Last verified", intel.last_verified_at),
                ("Source", intel.source),
            ],
        )
        if intel.contacts:
            lines += ["", "### Contact Roster (persona order)", ""]
            lines += _table(
                ("#", "Name", "Title", "Department", "Seniority", "Email", "Why"),
                [
                    (
                        str(index),
                        contact.name,
                        contact.title,
                        contact.department,
                        contact.seniority,
                        contact.email,
                        contact.rank_label,
                    )
                    for index, contact in enumerate(intel.contacts, start=1)
                ],
            )
        else:
            lines += ["", _unavailable("contact roster")]
        return lines

    @staticmethod
    def _battlecard_sections(context: _AskContext) -> list[str]:
        """Render the approved battlecard for every matched competitor footprint."""
        lines = ["## Approved Competitive Guidance", ""]
        if not context.vendors:
            return [*lines, _unavailable("installed vendor footprint")]
        if not context.matched_cards:
            return [
                *lines,
                f"Installed vendors on record: {_joined(context.vendors, 'none')}.",
                "",
                "_No approved battlecard in the local set matches these vendors, so no "
                "competitive claims are made here._",
            ]
        for vendor, card in context.matched_cards:
            lines += [
                f"### {card.competitor_name} (recorded as `{vendor}`)",
                "",
                f"**Value hook.** {card.value_hook or 'No value hook recorded.'}",
                "",
                f"**Kill points.** {card.kill_points or 'No kill points recorded.'}",
                "",
                "**Known weaknesses**",
                "",
                *_bullets(card.weaknesses or ("No weaknesses recorded.",)),
                "",
                "**Trap questions to ask**",
                "",
                *_numbered(card.trap_questions or ("No trap questions recorded.",)),
                "",
                f"_Source: {card.source}._",
                "",
            ]
        if context.unmatched_vendors:
            lines += [
                "### Vendors without an approved card",
                "",
                *_bullets(
                    f"`{vendor}` — no approved card; do not improvise competitive claims."
                    for vendor in context.unmatched_vendors
                ),
            ]
        return lines

    @staticmethod
    def _gap_reasons(context: _AskContext) -> tuple[str, ...]:
        """Summarize the qualification gaps visible in the account record."""
        account = context.named_account
        gaps: list[str] = []
        if not account.bva_complete:
            gaps.append(
                "No completed business value assessment is recorded, so the economic "
                "case is unproven."
            )
        if account.stakeholder_count <= 1:
            gaps.append(
                f"Only {account.stakeholder_count} stakeholder is engaged, which leaves "
                "the deal single-threaded."
            )
        elif account.stakeholder_count < 3:
            gaps.append(
                f"{account.stakeholder_count} stakeholders are engaged; add an economic "
                "buyer or technical owner to reach committee coverage."
            )
        if account.days_in_stage > 30:
            gaps.append(
                f"The opportunity has been in {account.stage_display} for "
                f"{account.days_in_stage} days, well past a healthy stage age."
            )
        if _stage_rank(account.stage) < 20:
            gaps.append(
                "The stage is still early, so qualification should be confirmed before "
                "forecasting."
            )
        if context.intent is None:
            gaps.append("No intent signal is on record to corroborate buying activity.")
        if context.intel is None:
            gaps.append("No technographic record is on file to ground the vendor footprint.")
        return tuple(gaps)

    # -- Renderers: prospect ------------------------------------------------

    def _render_cold_call_coaching(self, context: _AskContext) -> list[str]:
        """Coach a live cold call for the focus account."""
        account = context.named_account
        intent = context.intent
        contact = context.primary_contact
        target = (
            f"{contact.name}, {contact.title}"
            if contact
            else "the most senior identity or security owner you can reach"
        )
        hook = (
            f"a recorded {intent.buying_stage.lower()}-stage research signal on "
            f"{intent.lead_topic.lower()}"
            if intent
            else "the vendor footprint recorded on the account"
        )
        trap_questions = [
            question for _, card in context.matched_cards for question in card.trap_questions
        ]

        lines = [
            f"**Call target:** {target}",
            f"**Grounded in:** {hook}",
            f"**Account context:** {account.industry}, {account.employee_count:,} employees, "
            f"{account.revenue_display} annual revenue, {account.territory}.",
            "",
            "## Call Objective",
            "",
            *_bullets(
                (
                    "Primary: earn a 20-minute discovery conversation with a dated slot.",
                    "Secondary: confirm who owns "
                    f"{intent.lead_topic.lower() if intent else 'identity security'} and how "
                    "that work is prioritized.",
                    "Tertiary: add one named stakeholder to the account "
                    f"(currently {account.stakeholder_count} engaged).",
                )
            ),
            "",
            "## Opener (say this, then stop talking)",
            "",
            f"> Hi {contact.first_name if contact else 'there'}, **(give your name and "
            "company)**. I will be direct about why I called and then you can tell me "
            "whether it is worth continuing.",
            "",
            f"> We work with {account.industry.lower()} organizations of about "
            f"{account.employee_count:,} people. What put {account.name} on my list is "
            f"{hook}.",
            "",
            "> Is identity access something your team is actively working on this quarter, "
            "or is it further out?",
            "",
            "## Permission and Pivot",
            "",
            *_numbered(
                (
                    "If yes: ask what triggered the work and who else is involved.",
                    "If not now: ask what is ahead of it, then ask for a 20-minute slot "
                    "in the following quarter.",
                    "If wrong person: ask for the name of the identity or access owner "
                    "before ending the call.",
                )
            ),
            "",
            "## Discovery Pivots",
            "",
        ]
        lines += _numbered(
            trap_questions[:4]
            or (
                "How do you decide today whether someone still needs the access they have?",
                "Who reviews access when a person changes roles?",
                "What happens when an auditor asks for evidence of access reviews?",
            )
        )
        lines += [
            "",
            "## Objection Handling",
            "",
        ]
        objection_rows: list[tuple[str, str]] = []
        for vendor, card in context.matched_cards:
            weakness = card.weaknesses[0] if card.weaknesses else "no recorded weakness"
            response = card.kill_points or card.value_hook or "Lead with governance outcomes."
            objection_rows.append((f"“We already use {vendor}.”", f"{response} Probe: {weakness}."))
        objection_rows += [
            (
                "“Send me some information.”",
                "Agree, then ask one qualifying question so the material is relevant, "
                "and book the follow-up before hanging up.",
            ),
            (
                "“We have no budget.”",
                "Do not discuss price. Ask what would have to be true for this to be "
                "funded in the next planning cycle.",
            ),
            (
                "“Not a priority.”",
                "Ask what is a priority, and whether identity access is part of any "
                "audit or compliance commitment this year.",
            ),
        ]
        lines += _table(("Objection", "Response"), objection_rows)
        lines += [
            "",
            "## Voicemail (under 20 seconds)",
            "",
            f"> Calling about {intent.lead_topic.lower() if intent else 'identity access'} at "
            f"{account.name}. I will send a short note as well. Two sentences, one question, "
            "then I will get out of your way.",
            "",
            "## Coaching Rubric (score yourself out of 10)",
            "",
            *_table(
                ("Skill", "What good looks like", "Weight"),
                [
                    ("Opener discipline", "Reason for the call stated in under 15 seconds", "20%"),
                    ("Silence after the ask", "You stopped and let them answer", "20%"),
                    (
                        "Question quality",
                        "Open questions about their process, not our product",
                        "25%",
                    ),
                    ("Objection handling", "You probed once before responding", "20%"),
                    ("Close", "A specific day and time was requested", "15%"),
                ],
            ),
            "",
            "## Log After the Call",
            "",
            *_bullets(
                (
                    "Named contact reached and their role.",
                    "Their words describing the current process.",
                    "Agreed next step with a date.",
                    f"Whether the stakeholder count should move above {account.stakeholder_count}.",
                )
            ),
        ]
        return lines

    def _render_pitch_practice(self, context: _AskContext) -> list[str]:
        """Run a structured pitch rehearsal for the focus account."""
        account = context.named_account
        intent = context.intent
        hook = context.matched_cards[0][1].value_hook if context.matched_cards else ""
        topics = intent.intent_topics if intent else ()

        lines = [
            f"**Rehearsal target:** a 90-second pitch for {account.name} "
            f"({account.industry}, {account.territory}).",
            f"**Anchor facts:** {account.employee_count:,} employees, "
            f"{account.revenue_display} annual revenue, installed footprint "
            f"{account.products_display}.",
            "",
            "## Script (90 seconds, three beats)",
            "",
            "### Beat 1 — Situation (25 seconds)",
            "",
            f"> {account.name} runs a {account.industry.lower()} environment with about "
            f"{account.employee_count:,} people"
            + (
                f", and {account.products_display} is already in place for identity."
                if account.current_products
                else ", and no identity products are recorded on the account yet."
            ),
            "",
            "### Beat 2 — Tension (35 seconds)",
            "",
        ]
        if topics:
            lines += [
                "> Your teams are actively researching "
                f"{_joined(tuple(topics[:2]), 'identity security')}. That pattern usually "
                "means access decisions are being made faster than they can be reviewed.",
            ]
        else:
            lines += [
                "> No research signal is recorded for this account, so keep the tension "
                "generic: access grows faster than the review process that governs it.",
            ]
        lines += [
            "",
            "### Beat 3 — Resolution and ask (30 seconds)",
            "",
            "> "
            + (
                hook
                or "One governed view of who has access, why, and whether it is still needed."
            ),
            "",
            "> Worth 20 minutes to compare how you handle access reviews today against how "
            "similar teams handle them?",
            "",
            "## Practice Drills",
            "",
            *_table(
                ("Round", "Constraint", "What it trains"),
                [
                    ("1", "Deliver the full script out loud, timed", "Structure and pacing"),
                    ("2", "Cut to 45 seconds without losing the ask", "Ruthless prioritization"),
                    (
                        "3",
                        "Deliver it as three questions instead of statements",
                        "Discovery reflex",
                    ),
                    (
                        "4",
                        "Deliver it to a peer playing the recorded persona",
                        "Handling interruption",
                    ),
                ],
            ),
            "",
            "## Expected Pushbacks",
            "",
        ]
        pushbacks: list[str] = []
        for vendor, card in context.matched_cards:
            pushbacks.append(
                f"“{vendor} already covers this.” — Recorded weakness to probe: "
                f"{card.weaknesses[0] if card.weaknesses else 'none recorded'}."
            )
        if intent and intent.buying_stage.lower() == "awareness":
            pushbacks.append(
                "“We are just looking.” — The recorded stage is Awareness, so aim for a "
                "learning conversation, not a commercial one."
            )
        if not account.bva_complete:
            pushbacks.append(
                "“What is the business case?” — No BVA is recorded; do not quote savings "
                "figures, offer to build the case together."
            )
        lines += _bullets(pushbacks or ("No account-specific pushbacks are derivable.",))
        lines += [
            "",
            "## Self-Scoring Sheet",
            "",
            *_table(
                ("Dimension", "Pass condition"),
                [
                    ("Time", "Between 75 and 100 seconds"),
                    ("Facts", "Every number spoken appears on the account record"),
                    ("Jargon", "No unexplained product names"),
                    ("Ask", "Ends with one specific, answerable question"),
                    ("Recall", "You did not read from the script on round three"),
                ],
            ),
            "",
            "## Facts You May Cite",
            "",
            *_bullets(
                (
                    f"Industry: {account.industry}",
                    f"Employees: {account.employee_count:,}",
                    f"Annual revenue: {account.revenue_display}",
                    f"Installed footprint: {account.products_display}",
                    "Recorded intent topics: "
                    + (intent.topics_display if intent else "none recorded"),
                )
            ),
            "",
            "_Anything not in this list is not established for this account. Do not assert it._",
        ]
        return lines

    def _render_top_prospect_accounts(self, context: _AskContext) -> list[str]:
        """Rank the supplied portfolio by an explainable prospecting score."""
        scored = sorted(
            (self._prospect_score(item, context.intent_for(item)) for item in context.accounts),
            key=lambda item: (-item.score, item.account.name),
        )
        lines = [
            f"**Accounts evaluated:** {len(scored)}",
            f"**Territories represented:** "
            f"{_joined(tuple(dict.fromkeys(item.account.territory for item in scored)), 'none')}",
            "",
            "## Ranking",
            "",
            *_table(
                ("Rank", "Account", "Score", "Band", "Intent", "Fit", "Buying stage", "Tier"),
                [
                    (
                        str(index),
                        f"{item.account.name} (`{item.account.account_id}`)",
                        f"{item.score}/100",
                        item.band,
                        f"{item.intent.intent_score}" if item.intent else "not recorded",
                        item.intent.profile_fit if item.intent else "not recorded",
                        item.intent.buying_stage if item.intent else "not recorded",
                        item.account.target_tier,
                    )
                    for index, item in enumerate(scored, start=1)
                ],
            ),
            "",
            "## Why Each Account Scored This Way",
            "",
        ]
        for index, item in enumerate(scored, start=1):
            lines += [
                f"### {index}. {item.account.name} — {item.score}/100 ({item.band})",
                "",
                *_bullets(item.reasons),
                "",
                f"**Recorded topics:** "
                f"{item.intent.topics_display if item.intent else 'none recorded'}",
                f"**Installed footprint:** {item.account.products_display}",
                f"**Open opportunity:** {_money(item.account.open_opportunity_amount)} · "
                f"**Stage:** {item.account.stage_display} · "
                f"**Owner:** {item.account.owner_id}",
                "",
            ]
        lines += [
            "## Scoring Method",
            "",
            *_bullets(
                (
                    "60% of the recorded intent score.",
                    "Buying stage: Decision 10, Consideration 6, Awareness 2.",
                    "Profile fit: Strong 15, Moderate 8, Weak 0.",
                    "Target tier: Tier 1 15, Tier 2 8, anything else 5.",
                    "Capped at 100. Accounts without an intent signal lose the intent, "
                    "stage, and fit components.",
                )
            ),
            "",
            "Bands: 80 and above Work now, 60 to 79 Work this week, 40 to 59 Nurture, "
            "below 40 Hold.",
        ]
        return lines

    @staticmethod
    def _prospect_score(
        account: _AccountFacts, intent: _IntentFacts | None
    ) -> _ScoredAccount:
        """Score one account for prospecting priority, with reasons."""
        reasons: list[str] = []
        score = 0.0
        if intent is None:
            reasons.append("No intent signal on record, so intent, stage, and fit score zero.")
        else:
            score += 0.6 * intent.intent_score
            reasons.append(
                f"Intent score {intent.intent_score}/100 from {intent.source} contributes "
                f"{0.6 * intent.intent_score:.0f} points."
            )
            stage_points = {"decision": 10, "consideration": 6, "awareness": 2}.get(
                intent.buying_stage.lower(), 0
            )
            score += stage_points
            reasons.append(
                f"Buying stage {intent.buying_stage} contributes {stage_points} points."
            )
            fit_points = {"strong": 15, "moderate": 8, "weak": 0}.get(
                intent.profile_fit.lower(), 0
            )
            score += fit_points
            reasons.append(f"Profile fit {intent.profile_fit} contributes {fit_points} points.")
        tier_points = {"tier 1": 15, "tier 2": 8}.get(account.target_tier.lower(), 5)
        score += tier_points
        reasons.append(f"Target tier {account.target_tier} contributes {tier_points} points.")

        total = min(100, int(round(score)))
        band = (
            "Work now"
            if total >= 80
            else "Work this week"
            if total >= 60
            else "Nurture"
            if total >= 40
            else "Hold"
        )
        return _ScoredAccount(
            account=account,
            intent=intent,
            score=total,
            band=band,
            reasons=tuple(reasons),
            motion="Prospect",
        )

    def _render_intel_analysis(self, context: _AskContext) -> list[str]:
        """Analyze technographic and intent intelligence for the focus account."""
        account = context.named_account
        intel = context.intel
        lines = [
            f"**Subject:** {account.name} (`{account.domain}`), {account.industry}, "
            f"{account.territory}.",
            "",
            "## Findings",
            "",
        ]
        findings: list[str] = []
        if intel is not None:
            ratio = (
                account.employee_count / intel.it_security_headcount
                if intel.it_security_headcount
                else 0.0
            )
            findings.append(
                f"{len(intel.installed_technologies)} technologies are on record: "
                f"{intel.technologies_display}."
            )
            findings.append(
                f"IT security headcount of {intel.it_security_headcount:,} against "
                f"{account.employee_count:,} employees"
                + (
                    f" is roughly one security person per {ratio:,.0f} employees."
                    if ratio
                    else " cannot be expressed as a ratio because headcount is zero."
                )
            )
            findings.append(
                f"{len(intel.contacts)} contacts are known across "
                f"{len(intel.departments)} departments "
                f"({_joined(intel.departments, 'none recorded')})."
            )
            findings.append(f"Record last verified {intel.last_verified_at} by {intel.source}.")
        else:
            findings.append("No technographic record was supplied, so vendor analysis is limited.")
        overlap = tuple(
            product
            for product in account.current_products
            if intel is not None
            and any(
                _normalize_vendor(product) == _normalize_vendor(technology)
                for technology in intel.installed_technologies
            )
        )
        findings.append(
            f"CRM products ({account.products_display}) and technographics agree on: "
            f"{_joined(overlap, 'no overlapping entries')}."
        )
        if context.intent is not None:
            findings.append(
                f"Intent is {context.intent.buying_stage} at "
                f"{context.intent.intent_score}/100 with {context.intent.profile_fit} fit, "
                f"observed {context.intent.observed_at}."
            )
        lines += _bullets(findings)

        lines += ["", *self._intel_section(intel), "", *self._intent_section(context.intent)]
        lines += ["", "## Competitive Footprint Read", ""]
        if context.matched_cards:
            lines += _table(
                ("Vendor on record", "Approved card", "Primary weakness to probe"),
                [
                    (
                        vendor,
                        card.competitor_name,
                        card.weaknesses[0] if card.weaknesses else "none recorded",
                    )
                    for vendor, card in context.matched_cards
                ],
            )
        else:
            lines.append(_unavailable("matched battlecard"))
        if context.unmatched_vendors:
            lines += [
                "",
                f"Vendors without an approved card: "
                f"{_joined(context.unmatched_vendors, 'none')}.",
            ]
        lines += [
            "",
            "## Intelligence Gaps to Close",
            "",
            *_bullets(
                self._gap_reasons(context)
                or ("No qualification gaps are visible in the current records.",)
            ),
        ]
        return lines

    def _render_messaging(self, context: _AskContext) -> list[str]:
        """Draft persona-specific messaging grounded in recorded facts."""
        account = context.named_account
        intent = context.intent
        contact = context.primary_contact
        topic = intent.lead_topic if intent else "identity access review"
        hook = (
            context.matched_cards[0][1].value_hook
            if context.matched_cards
            else "One governed view of who has access and whether it is still needed."
        )
        salutation = contact.first_name if contact else "there"

        lines = [
            "**Audience:** "
            + (
                f"{contact.name}, {contact.title}"
                if contact
                else "buying committee not yet identified"
            ),
            f"**Evidence used:** recorded topic “{topic}”, installed footprint "
            f"{account.products_display}, {account.industry} at "
            f"{account.employee_count:,} employees.",
            "",
            "## Core Message",
            "",
            *_bullets(
                (
                    f"**Who:** {account.industry} organizations of roughly "
                    f"{account.employee_count:,} people.",
                    f"**Observed:** {topic} is a recorded area of research"
                    + (
                        f" at {intent.buying_stage} stage with {intent.profile_fit} fit."
                        if intent
                        else "; no signal strength is recorded."
                    ),
                    f"**Point of view:** {hook}",
                    "**Ask:** a 20-minute working conversation with a named date.",
                )
            ),
            "",
            "## Email",
            "",
            f"**Subject:** {topic} at {account.name}",
            "",
            f"> Hi {salutation},",
            ">",
            f"> {topic} came up as an active area for {account.industry.lower()} teams of "
            f"your size, and {account.name} already runs {account.products_display}.",
            ">",
            f"> {hook}",
            ">",
            "> Would a 20-minute conversation next Tuesday be useful to compare how you "
            "handle access reviews today?",
            "",
            "## Call Opening",
            "",
            f"> Hi {salutation}, I called because {topic.lower()} is an active topic for "
            f"teams like yours. I would like to understand how {account.name} decides "
            "whether someone still needs their access. Is that your area?",
            "",
            "## LinkedIn Note (under 300 characters)",
            "",
            f"> Hi {salutation} — {topic.lower()} keeps coming up with "
            f"{account.industry.lower()} teams of your size. {hook} Open to 20 minutes to "
            "compare notes?",
            "",
            "## Persona Variants",
            "",
        ]
        if context.intel is not None and context.intel.contacts:
            lines += _table(
                ("Persona", "Lead with", "Avoid"),
                [
                    (
                        f"{item.name} — {item.title}",
                        {
                            0: "Risk exposure, audit outcomes, and program accountability.",
                            1: "Program scope, staffing effort, and delivery timelines.",
                            2: "Evaluation criteria, integration effort, and rollout plan.",
                            3: "Day-to-day operational load and ticket volume.",
                            4: "Business impact on their own team's access needs.",
                        }[item.rank],
                        {
                            0: "Feature depth and console walkthroughs.",
                            1: "Executive abstractions without a plan.",
                            2: "Commercial terms before technical fit.",
                            3: "Strategy language without operational specifics.",
                            4: "Security jargon without translation.",
                        }[item.rank],
                    )
                    for item in context.intel.contacts
                ],
            )
        else:
            lines.append(_unavailable("contact roster, so persona variants cannot be tailored"))
        lines += [
            "",
            "## Proof Themes You May Use",
            "",
            *_bullets(
                tuple(
                    f"{card.competitor_name}: {card.kill_points}"
                    for _, card in context.matched_cards
                    if card.kill_points
                )
                or ("No approved proof themes match this account's footprint.",)
            ),
            "",
            "## Guardrails",
            "",
            *_bullets(
                (
                    "Cite only the account, intent, and technographic fields listed above.",
                    "Do not quote savings percentages; no business value assessment is "
                    f"recorded as complete ({'yes' if account.bva_complete else 'no'}).",
                    "Avoid unexplained product names and superlatives.",
                    "One question per message, and one dated ask.",
                )
            ),
        ]
        return lines

    def _render_territory_whitespace(self, context: _AskContext) -> list[str]:
        """Map footprint and engagement whitespace across the supplied portfolio."""
        accounts = sorted(context.accounts, key=lambda item: (item.territory, item.name))
        vendor_catalog = tuple(
            dict.fromkeys(
                product for account in accounts for product in account.current_products
            )
        )
        total_pipeline = sum(item.open_opportunity_amount for item in accounts)

        lines = [
            f"**Accounts in scope:** {len(accounts)}",
            f"**Territories:** "
            f"{_joined(tuple(dict.fromkeys(item.territory for item in accounts)), 'none')}",
            f"**Recorded open pipeline:** {_money(total_pipeline)}",
            "",
            "## Territory Rollup",
            "",
            *_table(
                ("Territory", "Accounts", "Open pipeline", "Tiers", "Stages"),
                [
                    (
                        territory,
                        str(len(group)),
                        _money(sum(item.open_opportunity_amount for item in group)),
                        _joined(tuple(dict.fromkeys(item.target_tier for item in group)), "none"),
                        _joined(
                            tuple(dict.fromkeys(item.stage_display for item in group)), "none"
                        ),
                    )
                    for territory, group in self._grouped(accounts, lambda item: item.territory)
                ],
            ),
            "",
            "## Installed Vendor Footprint Matrix",
            "",
        ]
        if vendor_catalog:
            lines += _table(
                ("Account", *vendor_catalog),
                [
                    (
                        account.name,
                        *(
                            "Installed" if vendor in account.current_products else "—"
                            for vendor in vendor_catalog
                        ),
                    )
                    for account in accounts
                ],
            )
            lines += [
                "",
                "_The columns are the vendors observed across these accounts; a dash means "
                "the vendor is not on that account's record, not that it is absent from the "
                "environment._",
            ]
        else:
            lines.append(_unavailable("installed product data across these accounts"))

        lines += ["", "## Whitespace Signals", ""]
        rows: list[tuple[str, str, str, str]] = []
        for account in accounts:
            signals: list[str] = []
            if account.open_opportunity_amount == 0:
                signals.append("no open pipeline")
            if not account.stage:
                signals.append("no recorded stage")
            if account.stakeholder_count <= 1:
                signals.append("single-threaded")
            if not account.bva_complete:
                signals.append("no value case")
            if account.days_in_stage > 30:
                signals.append(f"{account.days_in_stage} days in stage")
            if len(account.current_products) <= 1:
                signals.append("narrow vendor footprint")
            intent = context.intent_for(account)
            if intent is None:
                signals.append("no intent signal")
            rows.append(
                (
                    account.name,
                    account.territory,
                    _joined(tuple(signals), "no whitespace signals"),
                    f"{intent.intent_score}/100" if intent else "not recorded",
                )
            )
        lines += _table(("Account", "Territory", "Whitespace signals", "Intent"), rows)

        uncovered = tuple(item for item in accounts if item.open_opportunity_amount == 0)
        lines += [
            "",
            "## Coverage Actions",
            "",
            *_bullets(
                (
                    f"Accounts with zero open pipeline: "
                    f"{_joined(tuple(item.name for item in uncovered), 'none')}.",
                    "Accounts that are single-threaded: "
                    + _joined(
                        tuple(
                            item.name for item in accounts if item.stakeholder_count <= 1
                        ),
                        "none",
                    )
                    + ".",
                    "Accounts without a completed value case: "
                    + _joined(
                        tuple(item.name for item in accounts if not item.bva_complete), "none"
                    )
                    + ".",
                    "Accounts past 30 days in stage: "
                    + _joined(
                        tuple(item.name for item in accounts if item.days_in_stage > 30), "none"
                    )
                    + ".",
                )
            ),
        ]
        return lines

    @staticmethod
    def _grouped(
        accounts: Sequence[_AccountFacts],
        key: Callable[[_AccountFacts], str],
    ) -> tuple[tuple[str, tuple[_AccountFacts, ...]], ...]:
        """Group accounts by ``key`` deterministically, preserving sorted key order."""
        buckets: dict[str, list[_AccountFacts]] = {}
        for account in accounts:
            buckets.setdefault(key(account), []).append(account)
        return tuple((name, tuple(buckets[name])) for name in sorted(buckets))

    def _render_top_upsell_target(self, context: _AskContext) -> list[str]:
        """Rank expansion targets and label the recommended motion for each."""
        candidates = [
            item
            for item in context.accounts
            if item.current_products or item.open_opportunity_amount > 0
        ]
        scored = sorted(
            (self._upsell_score(item, context.intent_for(item)) for item in candidates),
            key=lambda item: (-item.score, item.account.name),
        )
        lines = [
            f"**Accounts with an existing footprint or open pipeline:** {len(scored)} of "
            f"{len(context.accounts)} supplied.",
            "",
        ]
        if not scored:
            lines += [
                _unavailable("account with recorded products or open pipeline"),
                "",
                "Expansion ranking needs at least one account with a `current_products` "
                "entry or a non-zero `open_opportunity_amount`.",
            ]
            return lines

        best = scored[0]
        lines += [
            "## Recommended Target",
            "",
            f"**{best.account.name}** (`{best.account.account_id}`) — {best.score}/100, "
            f"motion **{best.motion}**.",
            "",
            *_bullets(best.reasons),
            "",
            "## Full Ranking",
            "",
            *_table(
                ("Rank", "Account", "Score", "Motion", "Footprint", "Open pipeline", "Committee"),
                [
                    (
                        str(index),
                        item.account.name,
                        f"{item.score}/100",
                        item.motion,
                        item.account.products_display,
                        _money(item.account.open_opportunity_amount),
                        str(item.account.stakeholder_count),
                    )
                    for index, item in enumerate(scored, start=1)
                ],
            ),
            "",
            "## Motion Rules",
            "",
            *_table(
                ("Motion", "Rule applied", "First move"),
                [
                    (
                        "True-up",
                        "Employee count of 20,000 or more, so entitlement drift is likely",
                        "Compare contracted entitlement against the recorded employee count",
                    ),
                    (
                        "Cross-sell",
                        "One or fewer products on record, so adjacent scope is untouched",
                        "Introduce the adjacent capability area that matches recorded intent",
                    ),
                    (
                        "Upsell",
                        "Multi-product footprint below the true-up threshold",
                        "Expand depth within the existing footprint before adding scope",
                    ),
                ],
            ),
            "",
            "## Scoring Method",
            "",
            *_bullets(
                (
                    "40% of the recorded intent score.",
                    "Annual revenue: 5B and above 20, 3B and above 14, 1B and above 8, "
                    "otherwise 4.",
                    "Employees: 20,000 and above 15, 10,000 and above 10, 5,000 and above 6, "
                    "otherwise 3.",
                    "Open pipeline above zero adds 10.",
                    "Engaged stakeholders: 3 or more 10, exactly 2 6, otherwise 2.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    @staticmethod
    def _upsell_score(
        account: _AccountFacts, intent: _IntentFacts | None
    ) -> _ScoredAccount:
        """Score one account for expansion potential and classify its motion."""
        reasons: list[str] = []
        score = 0.0
        if intent is None:
            reasons.append("No intent signal on record, so the intent component scores zero.")
        else:
            score += 0.4 * intent.intent_score
            reasons.append(
                f"Intent score {intent.intent_score}/100 ({intent.buying_stage}) contributes "
                f"{0.4 * intent.intent_score:.0f} points."
            )
        if account.annual_revenue >= 5_000_000_000:
            revenue_points = 20
        elif account.annual_revenue >= 3_000_000_000:
            revenue_points = 14
        elif account.annual_revenue >= 1_000_000_000:
            revenue_points = 8
        else:
            revenue_points = 4
        score += revenue_points
        reasons.append(
            f"Annual revenue {account.revenue_display} contributes {revenue_points} points."
        )

        if account.employee_count >= 20_000:
            seat_points = 15
        elif account.employee_count >= 10_000:
            seat_points = 10
        elif account.employee_count >= 5_000:
            seat_points = 6
        else:
            seat_points = 3
        score += seat_points
        reasons.append(
            f"{account.employee_count:,} employees contribute {seat_points} points."
        )

        pipeline_points = 10 if account.open_opportunity_amount > 0 else 0
        score += pipeline_points
        reasons.append(
            f"Open pipeline {_money(account.open_opportunity_amount)} contributes "
            f"{pipeline_points} points."
        )

        committee_points = (
            10 if account.stakeholder_count >= 3 else 6 if account.stakeholder_count == 2 else 2
        )
        score += committee_points
        reasons.append(
            f"{account.stakeholder_count} engaged stakeholders contribute "
            f"{committee_points} points."
        )

        if account.employee_count >= 20_000:
            motion = "True-up"
        elif len(account.current_products) <= 1:
            motion = "Cross-sell"
        else:
            motion = "Upsell"
        reasons.append(
            f"Motion is {motion} based on {account.employee_count:,} employees and "
            f"{len(account.current_products)} recorded product(s)."
        )

        total = min(100, int(round(score)))
        band = (
            "Pursue now"
            if total >= 80
            else "Build the case"
            if total >= 60
            else "Nurture"
            if total >= 40
            else "Hold"
        )
        return _ScoredAccount(
            account=account,
            intent=intent,
            score=total,
            band=band,
            reasons=tuple(reasons),
            motion=motion,
        )

    # -- Renderers: plan ----------------------------------------------------

    def _render_account_360_healthcheck(self, context: _AskContext) -> list[str]:
        """Score account health across six deterministic dimensions."""
        account = context.named_account
        intent = context.intent

        engagement = (
            100
            if account.days_in_stage <= 14
            else 80
            if account.days_in_stage <= 30
            else 55
            if account.days_in_stage <= 45
            else 30
        )
        committee = min(100, account.stakeholder_count * 30)
        value_case = 100 if account.bva_complete else 25
        if account.open_opportunity_amount >= 1_000_000:
            pipeline = 100
        elif account.open_opportunity_amount >= 750_000:
            pipeline = 85
        elif account.open_opportunity_amount >= 500_000:
            pipeline = 70
        elif account.open_opportunity_amount >= 250_000:
            pipeline = 55
        elif account.open_opportunity_amount > 0:
            pipeline = 40
        else:
            pipeline = 0
        intent_points = intent.intent_score if intent else 0
        coverage = 100 if (intent and context.intel) else 60 if (intent or context.intel) else 20

        dimensions: tuple[tuple[str, int, str], ...] = (
            (
                "Engagement",
                engagement,
                f"{account.days_in_stage} days in {account.stage_display}; last activity "
                f"{account.last_activity_date}.",
            ),
            (
                "Committee coverage",
                committee,
                f"{account.stakeholder_count} engaged stakeholder(s) on record.",
            ),
            (
                "Value case",
                value_case,
                "BVA complete." if account.bva_complete else "No completed BVA on record.",
            ),
            (
                "Pipeline",
                pipeline,
                f"{_money(account.open_opportunity_amount)} open against "
                f"{account.revenue_display} annual revenue.",
            ),
            (
                "Buying intent",
                intent_points,
                f"{intent.intent_score}/100, {intent.buying_stage}, {intent.profile_fit} fit."
                if intent
                else "No intent signal on record.",
            ),
            (
                "Signal coverage",
                coverage,
                "Intent and technographic records present."
                if (intent and context.intel)
                else "One enrichment source present."
                if (intent or context.intel)
                else "No enrichment records supplied.",
            ),
        )
        overall = int(round(sum(item[1] for item in dimensions) / len(dimensions)))
        band = (
            "Healthy"
            if overall >= 80
            else "Watch"
            if overall >= 60
            else "At risk"
            if overall >= 40
            else "Critical"
        )

        lines = [
            f"**Overall health:** {overall}/100 — **{band}**",
            f"**Owner:** {account.owner_id} · **Territory:** {account.territory} · "
            f"**Tier:** {account.target_tier}",
            "",
            "## Health by Dimension",
            "",
            *_table(
                ("Dimension", "Score", "Evidence"),
                [(name, f"{score}/100", evidence) for name, score, evidence in dimensions],
            ),
            "",
            "## Red Flags",
            "",
            *_bullets(
                self._gap_reasons(context) or ("No red flags are visible in the records.",)
            ),
            "",
            "## Strengths",
            "",
        ]
        strengths = [
            f"{name} scores {score}/100 — {evidence}"
            for name, score, evidence in dimensions
            if score >= 80
        ]
        lines += _bullets(strengths or ("No dimension currently scores 80 or above.",))
        lines += [
            "",
            "## Next Three Actions",
            "",
            *_numbered(self._next_actions(context)[:3]),
            "",
            *self._account_snapshot(account),
            "",
            *self._intent_section(intent),
            "",
            *self._intel_section(context.intel),
            "",
            "## Scoring Method",
            "",
            *_bullets(
                (
                    "Engagement from days in stage: 14 or fewer 100, 30 or fewer 80, "
                    "45 or fewer 55, otherwise 30.",
                    "Committee coverage is engaged stakeholders times 30, capped at 100.",
                    "Value case is 100 when the BVA is complete, otherwise 25.",
                    "Pipeline is banded from the open opportunity amount.",
                    "Buying intent is the recorded intent score, or zero when absent.",
                    "Signal coverage reflects how many enrichment records were supplied.",
                    "Overall health is the unweighted mean of the six dimensions.",
                )
            ),
        ]
        return lines

    @staticmethod
    def _next_actions(context: _AskContext) -> tuple[str, ...]:
        """Derive prioritized next actions from the account record."""
        account = context.named_account
        intent = context.intent
        actions: list[str] = []
        if account.stakeholder_count <= 1:
            actions.append(
                "Add a second stakeholder this week; the account is single-threaded at "
                f"{account.stakeholder_count} engaged contact."
            )
        if not account.bva_complete:
            actions.append(
                "Book a value working session to start the business value assessment, "
                "which is not marked complete."
            )
        if account.days_in_stage > 30:
            actions.append(
                f"Reconfirm the compelling event: {account.days_in_stage} days in "
                f"{account.stage_display} indicates a stalled stage."
            )
        next_code, next_objective = _next_stage(account.stage)
        actions.append(
            f"Drive toward {next_code}: {next_objective.lower()}."
        )
        if intent is not None and intent.buying_stage.lower() == "decision":
            actions.append(
                "Intent is at Decision stage; propose a commercial next step and a dated "
                "decision timeline."
            )
        elif intent is not None:
            actions.append(
                f"Intent is at {intent.buying_stage} stage on "
                f"{intent.lead_topic.lower()}; keep the next step educational and specific."
            )
        else:
            actions.append(
                "Request an intent signal refresh; there is no recorded buying signal to "
                "prioritize against."
            )
        if context.intel is None:
            actions.append(
                "Enrich the account with a technographic record so the vendor footprint and "
                "contact roster are grounded."
            )
        return tuple(actions)

    def _render_account_plan(self, context: _AskContext) -> list[str]:
        """Build a strategic account plan for the focus account."""
        account = context.named_account
        intent = context.intent
        next_code, next_objective = _next_stage(account.stage)

        lines = [
            f"**Plan owner:** {account.owner_id} · **Territory:** {account.territory} · "
            f"**Tier:** {account.target_tier}",
            f"**Current stage:** {account.stage_display} — {_stage_objective(account.stage)}",
            "",
            "## Where We Are",
            "",
            *_bullets(
                (
                    f"{account.name} is a {account.industry.lower()} organization with "
                    f"{account.employee_count:,} employees and {account.revenue_display} in "
                    "annual revenue.",
                    f"Recorded footprint: {account.products_display}.",
                    f"Open opportunity of {_money(account.open_opportunity_amount)} at stage "
                    f"{account.stage_display}, {account.days_in_stage} days in stage.",
                    f"{account.stakeholder_count} stakeholder(s) engaged; business value "
                    f"assessment {'complete' if account.bva_complete else 'not complete'}.",
                    f"Last recorded activity {account.last_activity_date}.",
                )
            ),
            "",
            "## Objectives for This Account",
            "",
            *_numbered(
                (
                    f"Advance from {account.stage_display} to {next_code} — "
                    f"{next_objective.lower()}.",
                    "Reach committee coverage of at least three engaged stakeholders "
                    f"(currently {account.stakeholder_count}).",
                    "Complete the business value assessment and get it acknowledged by the "
                    "economic buyer."
                    if not account.bva_complete
                    else "Keep the completed business value assessment current as scope changes.",
                    f"Convert the recorded interest in "
                    f"{intent.lead_topic.lower() if intent else 'identity security'} into an "
                    "agreed evaluation plan.",
                )
            ),
            "",
            "## Buying Committee",
            "",
        ]
        if context.intel is not None and context.intel.contacts:
            lines += _table(
                ("Contact", "Title", "Department", "Role in the plan"),
                [
                    (
                        contact.name,
                        contact.title,
                        contact.department,
                        contact.rank_label,
                    )
                    for contact in context.intel.contacts
                ],
            )
            lines += [
                "",
                f"The account records {account.stakeholder_count} engaged stakeholder(s) "
                f"against {len(context.intel.contacts)} known contact(s); close that gap "
                "before forecasting.",
            ]
        else:
            lines.append(_unavailable("contact roster"))

        lines += [
            "",
            "## Competitive Landscape",
            "",
            *self._battlecard_sections(context)[2:],
            "",
            "## Milestones",
            "",
            *_table(
                ("Stage", "Objective", "Status"),
                [
                    (
                        code,
                        objective,
                        "Complete"
                        if _stage_rank(code) < _stage_rank(account.stage)
                        else "Current"
                        if _stage_rank(code) == _stage_rank(account.stage)
                        else "Ahead",
                    )
                    for code, objective in STAGE_LADDER
                ],
            ),
            "",
            "## 30 / 60 / 90",
            "",
            "### Next 30 days",
            "",
            *_bullets(self._next_actions(context)[:3]),
            "",
            "### Days 31 to 60",
            "",
            *_bullets(
                (
                    f"Complete the work required to exit {account.stage_display} into "
                    f"{next_code}.",
                    "Run a joint value review with the economic buyer and capture their "
                    "own success measures.",
                    "Validate technical fit with the security operations owner.",
                )
            ),
            "",
            "### Days 61 to 90",
            "",
            *_bullets(
                (
                    "Agree the mutual action plan through commercial close.",
                    f"Align the commercial structure to the recorded "
                    f"{_money(account.open_opportunity_amount)} open amount.",
                    "Confirm the paper process, security review, and signature path.",
                )
            ),
            "",
            "## Risks to Manage",
            "",
            *_bullets(
                self._gap_reasons(context) or ("No qualification gaps are visible.",)
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_dmu_expansion(self, context: _AskContext) -> list[str]:
        """Plan expansion of the decision-making unit."""
        account = context.named_account
        intel = context.intel
        known = len(intel.contacts) if intel else 0
        gap = max(0, known - account.stakeholder_count)

        lines = [
            f"**Engaged stakeholders on record:** {account.stakeholder_count}",
            f"**Known contacts available:** {known}",
            f"**Immediately actionable gap:** {gap} known contact(s) not yet engaged",
            "",
            "## Coverage Read",
            "",
            *_bullets(
                (
                    f"The account records {account.stakeholder_count} engaged stakeholder(s), "
                    "which is "
                    + (
                        "single-threaded and the single largest structural risk."
                        if account.stakeholder_count <= 1
                        else "below committee coverage of three."
                        if account.stakeholder_count < 3
                        else "at or above committee coverage of three."
                    ),
                    f"Departments represented in the roster: "
                    f"{_joined(intel.departments if intel else (), 'none recorded')}.",
                    f"IT security headcount of "
                    f"{intel.it_security_headcount:,} suggests the program has dedicated "
                    "owners to find."
                    if intel
                    else "No technographic record, so security staffing is unknown.",
                )
            ),
            "",
            "## Known Contacts and Engagement Priority",
            "",
        ]
        if intel is not None and intel.contacts:
            lines += _table(
                ("Priority", "Contact", "Title", "Department", "Email", "Why engage"),
                [
                    (
                        str(index),
                        contact.name,
                        contact.title,
                        contact.department,
                        contact.email,
                        contact.rank_label,
                    )
                    for index, contact in enumerate(intel.contacts, start=1)
                ],
            )
        else:
            lines.append(_unavailable("contact roster, so no named expansion targets exist"))

        covered_ranks = {contact.rank for contact in intel.contacts} if intel else set()
        missing_roles = [
            label
            for rank, label in (
                (0, "Executive security owner (chief-level sponsor)"),
                (1, "Senior identity or access program owner"),
                (2, "Identity program or evaluation lead"),
                (3, "Security operations or identity operations owner"),
            )
            if rank not in covered_ranks
        ]
        lines += [
            "",
            "## Roles Still Missing From the Roster",
            "",
            *_bullets(
                missing_roles
                or ("Every persona tier from executive through operations is represented.",)
            ),
            "",
            "_Missing roles are inferred from the titles present in the roster, not from any "
            "assumption about the customer's organization chart._",
            "",
            "## Multithreading Plan",
            "",
            *_numbered(
                (
                    (
                        f"Ask {intel.contacts[0].first_name} for an introduction to the owner "
                        "of access reviews, naming the specific decision you need help with."
                        if intel and intel.contacts
                        else "Identify one named contact through research before attempting "
                        "referral, since no roster is on file."
                    ),
                    "Send a parallel, persona-specific note to a second tier so coverage does "
                    "not depend on one relationship.",
                    "Propose a working session with two roles present, and make the agenda "
                    "the reason both must attend.",
                    f"Record every new contact so the stakeholder count moves above "
                    f"{account.stakeholder_count}.",
                )
            ),
            "",
            "## Referral Request You Can Send",
            "",
            f"> Hi {intel.contacts[0].first_name if intel and intel.contacts else 'there'}, "
            "before we go further I want to make sure the right people shape this. Who owns "
            "access reviews day to day, and would it make sense to include them in the next "
            "conversation?",
            "",
            "## Exit Criteria",
            "",
            *_bullets(
                (
                    "At least three engaged stakeholders recorded on the account.",
                    "An executive sponsor and an operational owner both engaged.",
                    "One stakeholder able to describe the business impact in their own words.",
                )
            ),
        ]
        return lines

    def _render_opportunity_plan(self, context: _AskContext) -> list[str]:
        """Assemble a qualification and close plan for the open opportunity."""
        account = context.named_account
        intent = context.intent
        economics = context.named_economics
        contacts = context.intel.contacts if context.intel else ()
        economic_buyer = next((item for item in contacts if item.rank == 0), None)
        champion = next((item for item in contacts if item.rank in {1, 2}), None)
        next_code, next_objective = _next_stage(account.stage)

        lines = [
            f"**Opportunity value on record:** {_money(account.open_opportunity_amount)}",
            f"**Stage:** {account.stage_display} ({account.days_in_stage} days) — "
            f"{_stage_objective(account.stage)}",
            f"**Qualification state:** {economics.qualification_label}",
            "",
            "## Qualification Grid",
            "",
            *_table(
                ("Element", "What the record shows", "Gap to close"),
                [
                    (
                        "Metrics",
                        "BVA complete" if account.bva_complete else "No completed BVA",
                        "None"
                        if account.bva_complete
                        else "Agree measurable outcomes with the buyer and record them",
                    ),
                    (
                        "Economic buyer",
                        f"{economic_buyer.name}, {economic_buyer.title}"
                        if economic_buyer
                        else "No chief-level contact on record",
                        "None"
                        if economic_buyer
                        else "Identify and engage the executive security owner",
                    ),
                    (
                        "Decision criteria",
                        intent.topics_display if intent else "No recorded intent topics",
                        "Confirm which recorded topic is the decision driver"
                        if intent
                        else "Establish the criteria in discovery",
                    ),
                    (
                        "Decision process",
                        f"Stage {account.stage_display} on the local ladder",
                        f"Confirm the customer's own steps to reach {next_code}",
                    ),
                    (
                        "Identified pain",
                        f"Recorded research on {intent.lead_topic}"
                        if intent
                        else "No signal on record",
                        "Capture the customer's own description of the problem",
                    ),
                    (
                        "Champion",
                        f"{champion.name}, {champion.title}"
                        if champion
                        else "No senior program owner on record",
                        "None" if champion else "Develop a champion inside the identity program",
                    ),
                    (
                        "Competition",
                        _joined(context.vendors, "no vendors recorded"),
                        "Apply the approved battlecard for each matched vendor",
                    ),
                    (
                        "Paper process",
                        f"{economics.approval_owner} approves at this value",
                        "Confirm the customer's procurement and security review steps",
                    ),
                ],
            ),
            "",
            "## Close Plan",
            "",
            *_table(
                ("Step", "Owner", "Exit condition"),
                [
                    (
                        f"Exit {account.stage_display}",
                        account.owner_id,
                        _stage_objective(account.stage),
                    ),
                    (f"Enter {next_code}", account.owner_id, next_objective),
                    (
                        "Value case signed off",
                        economic_buyer.name if economic_buyer else "economic buyer to be named",
                        "Buyer restates the outcome measures in their own words",
                    ),
                    (
                        "Technical validation",
                        champion.name if champion else "program owner to be named",
                        "Success criteria agreed in writing",
                    ),
                    (
                        "Commercial agreement",
                        economics.approval_owner,
                        f"Structure agreed within the {economics.approved_discount_pct}% "
                        "guardrail",
                    ),
                    (
                        "Paper and signature",
                        "deal desk",
                        "Security review complete and signature path confirmed",
                    ),
                ],
            ),
            "",
            "## Risks",
            "",
            *_bullets(self._gap_reasons(context) or ("No qualification gaps are visible.",)),
            "",
            "## Immediate Actions",
            "",
            *_numbered(self._next_actions(context)),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_business_value_assessment(self, context: _AskContext) -> list[str]:
        """Scaffold the business value assessment for the focus account."""
        account = context.named_account
        intel = context.intel
        intent = context.intent
        economics = context.named_economics

        lines = [
            f"**Status on record:** BVA is "
            f"{'complete' if account.bva_complete else 'not complete'}.",
            f"**Investment reference:** {_money(account.open_opportunity_amount)} recorded as "
            f"the open opportunity amount "
            f"({_money(economics.annualized_amount)} per year over a "
            f"{economics.term_months}-month illustrative term).",
            "",
            "## Scope of the Assessment",
            "",
            *_table(
                ("Scope input", "Value on record"),
                [
                    ("Population", f"{account.employee_count:,} employees"),
                    (
                        "Security staffing",
                        f"{intel.it_security_headcount:,} IT security staff"
                        if intel
                        else "not recorded",
                    ),
                    ("Industry", account.industry),
                    ("Incumbent footprint", account.products_display),
                    ("Recorded research topics", intent.topics_display if intent else "none"),
                    ("Territory and tier", f"{account.territory}, {account.target_tier}"),
                ],
            ),
            "",
            "## Value Drivers to Quantify With the Customer",
            "",
        ]
        drivers: list[str] = []
        for topic in (intent.intent_topics if intent else ()):
            drivers.append(
                f"**{topic}** — ask the customer what this costs them today in effort, "
                "audit findings, or delay, and record their number, not ours."
            )
        for vendor, card in context.matched_cards:
            for weakness in card.weaknesses[:2]:
                drivers.append(
                    f"**{vendor}: {weakness}** — quantify the operational cost of this "
                    "recorded weakness in the customer's own environment."
                )
        lines += _bullets(
            drivers
            or (
                "No recorded intent topics or matched battlecards, so value drivers must be "
                "established in discovery before the assessment can be built.",
            )
        )
        lines += [
            "",
            "## Measurement Plan",
            "",
            *_table(
                ("Measure", "Baseline source", "Owner"),
                [
                    (
                        "Access review cycle time",
                        "Customer-provided baseline captured in discovery",
                        "Identity program owner",
                    ),
                    (
                        "Effort per certification campaign",
                        "Customer-provided baseline captured in discovery",
                        "Identity operations",
                    ),
                    (
                        "Audit findings related to access",
                        "Customer's own audit record",
                        "Executive sponsor",
                    ),
                    (
                        "Time to remove access on role change",
                        "Customer-provided baseline captured in discovery",
                        "Security operations",
                    ),
                ],
            ),
            "",
            "_Every baseline above is intentionally sourced from the customer. This build "
            "holds no benchmark data, so no savings figure is asserted here._",
            "",
            "## Investment Reference",
            "",
            *_table(
                ("Line", "Amount", "Basis"),
                [
                    (label, _money(amount), note)
                    for label, amount, note in economics.components
                ],
            ),
            "",
            "## Approval Path",
            "",
            *_bullets(
                (
                    f"Commercial approver at this value: {economics.approval_owner}.",
                    f"Qualification state: {economics.qualification_label} "
                    f"({account.stakeholder_count} stakeholder(s), BVA "
                    f"{'complete' if account.bva_complete else 'incomplete'}).",
                    "The assessment is not finished until the economic buyer restates the "
                    "outcome measures in their own words.",
                )
            ),
            "",
            "## Next Steps",
            "",
            *_numbered(
                (
                    "Book a 60-minute value working session with the economic buyer and the "
                    "program owner.",
                    "Capture baselines for each measure above, in the customer's numbers.",
                    "Return a one-page summary and ask the buyer to confirm or correct it.",
                    "Attach the confirmed summary to the opportunity and set `bva_complete`.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    # -- Renderers: engage --------------------------------------------------

    def _render_discovery_prep(self, context: _AskContext) -> list[str]:
        """Prepare a discovery conversation for the focus account."""
        account = context.named_account
        intent = context.intent
        contacts = context.intel.contacts if context.intel else ()
        trap_questions = [
            question for _, card in context.matched_cards for question in card.trap_questions
        ]

        lines = [
            f"**Meeting subject:** discovery with {account.name} "
            f"({account.industry}, {account.employee_count:,} employees)",
            f"**Stage objective:** {_stage_objective(account.stage)}",
            "",
            "## Agenda (45 minutes)",
            "",
            *_table(
                ("Minutes", "Segment", "Purpose"),
                [
                    ("0–5", "Frame and agree the agenda", "Confirm what a good use of time is"),
                    ("5–20", "Current process", "Understand how access decisions are made"),
                    ("20–33", "Impact and priority", "Establish why this matters now"),
                    ("33–40", "Decision process", "Learn who else is involved and how they buy"),
                    ("40–45", "Next step", "Agree a dated, specific next action"),
                ],
            ),
            "",
            "## Attendees on Record",
            "",
        ]
        if contacts:
            lines += _table(
                ("Contact", "Title", "Department", "What to learn from them"),
                [
                    (
                        contact.name,
                        contact.title,
                        contact.department,
                        {
                            0: "Business consequence and funding priority",
                            1: "Program scope, staffing, and timeline",
                            2: "Evaluation criteria and technical constraints",
                            3: "Operational load and current workarounds",
                            4: "Downstream impact on their team",
                        }[contact.rank],
                    )
                    for contact in contacts
                ],
            )
        else:
            lines.append(_unavailable("contact roster"))

        lines += [
            "",
            "## Hypotheses to Test (not to assert)",
            "",
        ]
        hypotheses = [
            f"As a {account.industry.lower()} organization with "
            f"{account.employee_count:,} employees, access review effort scales faster than "
            "the team reviewing it.",
        ]
        if intent is not None:
            hypotheses.append(
                f"Recorded research on {intent.lead_topic.lower()} at "
                f"{intent.buying_stage} stage suggests an active internal project."
            )
        if account.current_products:
            hypotheses.append(
                f"The recorded footprint ({account.products_display}) means governance and "
                "privileged access may be managed through separate processes."
            )
        if not account.bva_complete:
            hypotheses.append(
                "With no completed value case, the economic impact has not yet been "
                "articulated internally."
            )
        lines += _bullets(hypotheses)

        lines += [
            "",
            "## Question Bank",
            "",
            "### Approved trap questions",
            "",
            *_numbered(
                trap_questions[:6]
                or ("No approved trap questions match this account's footprint.",)
            ),
            "",
            "### Process questions",
            "",
            *_numbered(
                (
                    "Walk me through what happens today when someone changes roles.",
                    "Who signs off that access is still appropriate, and how often?",
                    "What evidence do you produce when an auditor asks about access?",
                    "Where does the current process break down most often?",
                )
            ),
            "",
            "### Priority and process questions",
            "",
            *_numbered(
                (
                    "What made this a priority now rather than last year?",
                    "Who else has to agree before something like this moves forward?",
                    "What has stopped a project like this in the past here?",
                    f"If this progresses, what does the path from here to a decision look "
                    f"like on your side? (Our record shows stage {account.stage_display}.)",
                )
            ),
            "",
            "## Must-Learn List",
            "",
            *_bullets(
                (
                    "The customer's own description of the problem.",
                    "One quantified measure of current effort or risk.",
                    "The names and roles of everyone who must agree.",
                    "A dated next step.",
                    f"Whether the {_money(account.open_opportunity_amount)} recorded on the "
                    "opportunity reflects their actual scope.",
                )
            ),
            "",
            "## Landmines to Avoid",
            "",
        ]
        landmines = [
            f"{card.competitor_name}: {question}"
            for _, card in context.matched_cards
            for question in card.trap_questions[:1]
        ]
        lines += _bullets(
            (
                *(f"Do not raise as a criticism, ask as a question — {item}" for item in landmines),
                "Do not quote savings figures; no completed value case is on record."
                if not account.bva_complete
                else "Keep the completed value case current if scope changes in this call.",
                "Do not name competitor weaknesses that are not on an approved card.",
            )
        )
        lines += ["", *self._intent_section(intent)]
        return lines

    def _render_post_meeting_notes(self, context: _AskContext) -> list[str]:
        """Produce a structured meeting record and a recap email."""
        account = context.named_account
        contact = context.primary_contact
        intent = context.intent
        next_code, next_objective = _next_stage(account.stage)

        lines = [
            f"**Account:** {account.name} (`{account.account_id}`) · "
            f"**Owner:** {account.owner_id}",
            f"**Stage at time of writing:** {account.stage_display}, "
            f"{account.days_in_stage} days in stage · "
            f"**Last recorded activity:** {account.last_activity_date}",
            "",
            "## Context Already on Record",
            "",
            *_bullets(
                (
                    f"{account.industry}, {account.employee_count:,} employees, "
                    f"{account.revenue_display} annual revenue.",
                    f"Installed footprint: {account.products_display}.",
                    f"Open opportunity: {_money(account.open_opportunity_amount)}.",
                    f"Engaged stakeholders: {account.stakeholder_count}; BVA "
                    f"{'complete' if account.bva_complete else 'incomplete'}.",
                    f"Recorded intent: {intent.buying_stage} at {intent.intent_score}/100 on "
                    f"{intent.topics_display}."
                    if intent
                    else "No intent signal on record.",
                )
            ),
            "",
            "## Meeting Record to Complete",
            "",
            *_table(
                ("Field", "Capture this"),
                [
                    ("Date and duration", "When the meeting happened and how long it ran"),
                    ("Attendees", "Every name and title present, on both sides"),
                    (
                        "Stated problem",
                        "The customer's own words describing what is not working",
                    ),
                    ("Current process", "How access decisions are made today, step by step"),
                    ("Quantified impact", "Any number the customer gave, in their units"),
                    ("Decision process", "Who must agree, and the steps they described"),
                    ("Competition mentioned", "Vendors the customer raised, unprompted"),
                    ("Objections raised", "Exact wording, and how you responded"),
                    ("Agreed next step", "The action, the owner, and the date"),
                    (
                        "Record updates",
                        f"Stage (now {account.stage_display}), stakeholder count "
                        f"(now {account.stakeholder_count}), BVA flag "
                        f"(now {'true' if account.bva_complete else 'false'})",
                    ),
                ],
            ),
            "",
            "_Fill these from what was said. Do not carry forward assumptions from the CRM "
            "record as if the customer confirmed them._",
            "",
            "## Recap Email",
            "",
            f"**To:** {contact.email if contact else 'the attendee list'}",
            f"**Subject:** Recap and next step — {account.name}",
            "",
            "_The three numbered lines are prompts. Replace each with what the customer "
            "actually said before sending; this build holds no meeting transcript._",
            "",
            f"> Hi {contact.first_name if contact else 'all'},",
            ">",
            "> Thank you for the time today. Here is what I heard, so you can correct me "
            "if I have it wrong:",
            ">",
            "> 1. The problem you described, in your words.",
            "> 2. How access decisions work today and where that breaks down.",
            "> 3. What has to be true for this to move forward on your side.",
            ">",
            f"> Our next step: the action and date you agreed. That keeps us on track for "
            f"{next_code.lower()} — {next_objective.lower()}.",
            ">",
            "> If I mischaracterized anything, reply and I will correct the record.",
            "",
            "## CRM Updates This Meeting Should Trigger",
            "",
            *_bullets(
                (
                    "Set `last_activity_date` to the meeting date.",
                    f"Update `stakeholder_count` if new named contacts attended "
                    f"(currently {account.stakeholder_count}).",
                    f"Re-evaluate `stage`; the record shows {account.stage_display} after "
                    f"{account.days_in_stage} days.",
                    "Set `bva_complete` only if the buyer confirmed the outcome measures."
                    if not account.bva_complete
                    else "Confirm the completed value case still matches the discussed scope.",
                    f"Adjust `open_opportunity_amount` if the discussed scope differs from "
                    f"{_money(account.open_opportunity_amount)}.",
                )
            ),
        ]
        return lines

    def _render_suggested_follow_up(self, context: _AskContext) -> list[str]:
        """Recommend the next best actions with owners and timing."""
        account = context.named_account
        intent = context.intent
        contact = context.primary_contact
        urgency = "Today" if account.days_in_stage > 30 else "Within two business days"

        actions = self._next_actions(context)
        lines = [
            f"**Urgency:** {urgency} — {account.days_in_stage} days in "
            f"{account.stage_display}, last activity {account.last_activity_date}.",
            "**Primary channel:** "
            + (
                f"email to {contact.name} ({contact.email})"
                if contact
                else "channel undetermined; no contact is on record"
            ),
            "",
            "## Prioritized Actions",
            "",
            *_table(
                ("Priority", "Action", "Owner", "When", "Why now"),
                [
                    (
                        str(index),
                        action,
                        account.owner_id,
                        urgency if index <= 2 else "This week",
                        "Derived from the account record fields cited in the action",
                    )
                    for index, action in enumerate(actions, start=1)
                ],
            ),
            "",
            "## Follow-Up Message",
            "",
            f"**To:** {contact.email if contact else 'contact to be identified'}",
            f"**Subject:** Next step on "
            f"{intent.lead_topic if intent else 'identity access'} — {account.name}",
            "",
            f"> Hi {contact.first_name if contact else 'there'},",
            ">",
            f"> Following up on {intent.lead_topic.lower() if intent else 'identity access'}. "
            + (
                f"Our record shows the last activity on "
                f"{account.last_activity_date}, so I want to make sure this has not gone "
                "quiet on my account."
                if account.days_in_stage > 30
                else "I want to keep momentum on the next step we discussed."
            ),
            ">",
            "> "
            + (
                "Would a short value working session with your economic buyer be useful? "
                "That is the piece still missing before we can talk seriously about scope."
                if not account.bva_complete
                else "Would it help to bring one more stakeholder into the next session so "
                "the evaluation does not depend on a single calendar?"
            ),
            ">",
            "> Happy to work around your schedule — does Tuesday or Thursday suit better?",
            "",
            "## If There Is No Reply",
            "",
            *_table(
                ("Day", "Channel", "Approach"),
                [
                    ("Day 0", "Email", "The message above, with one clear question"),
                    (
                        "Day 3",
                        "Phone",
                        "Reference the email in one sentence, then ask the same question",
                    ),
                    (
                        "Day 6",
                        "LinkedIn",
                        "Short note to a second stakeholder, not a repeat to the same person",
                    ),
                    (
                        "Day 10",
                        "Email",
                        "Offer to close the loop, and ask whether priorities have changed",
                    ),
                ],
            ),
            "",
            "## Signals That Change This Plan",
            "",
            *_bullets(
                (
                    f"Intent is currently {intent.buying_stage} at {intent.intent_score}/100; "
                    "a move toward Decision should accelerate the commercial next step."
                    if intent
                    else "No intent signal is on record; a new signal should reset this plan.",
                    f"Stakeholder count moving above {account.stakeholder_count} should shift "
                    "focus from access to consensus.",
                    "A completed value case should shift the ask to commercial structure."
                    if not account.bva_complete
                    else "The value case is complete, so the ask should be a dated decision "
                    "timeline.",
                )
            ),
        ]
        return lines

    def _render_digital_sales_room(self, context: _AskContext) -> list[str]:
        """Configure a shared digital sales room for the focus account."""
        account = context.named_account
        intent = context.intent
        contacts = context.intel.contacts if context.intel else ()
        next_code, next_objective = _next_stage(account.stage)

        lines = [
            f"**Room name:** {account.name} — Identity Program Workspace",
            f"**Room owner:** {account.owner_id} · **Account:** `{account.account_id}` · "
            f"**Domain:** {account.domain}",
            f"**Current stage:** {account.stage_display} — {_stage_objective(account.stage)}",
            "",
            "## Access List",
            "",
        ]
        if contacts:
            lines += _table(
                ("Invitee", "Title", "Email", "Access reason"),
                [
                    (
                        contact.name,
                        contact.title,
                        contact.email,
                        contact.rank_label,
                    )
                    for contact in contacts
                ],
            )
            lines += [
                "",
                f"Invite the {len(contacts)} known contact(s). The account records "
                f"{account.stakeholder_count} engaged stakeholder(s), so the room itself is a "
                "multithreading tool.",
            ]
        else:
            lines.append(
                _unavailable("contact roster, so the access list must be built from discovery")
            )

        lines += [
            "",
            "## Content Shelf",
            "",
            *_table(
                ("Shelf", "What to publish", "Grounded in"),
                [
                    (
                        "Why now",
                        f"A one-page summary of {intent.topics_display}"
                        if intent
                        else "A one-page summary of the agreed problem statement",
                        f"Recorded intent from {intent.source}"
                        if intent
                        else "Discovery notes only",
                    ),
                    (
                        "Current state",
                        f"The recorded footprint: {account.products_display}",
                        "Account `current_products`",
                    ),
                    (
                        "Competitive view",
                        _joined(
                            tuple(card.competitor_name for _, card in context.matched_cards),
                            "no matched cards, publish nothing competitive",
                        ),
                        "Approved battlecards",
                    ),
                    (
                        "Value case",
                        "The completed business value assessment"
                        if account.bva_complete
                        else "The value working-session agenda, since no BVA is complete",
                        "Account `bva_complete`",
                    ),
                    (
                        "Commercial",
                        f"Scope reference at {_money(account.open_opportunity_amount)}",
                        "Account `open_opportunity_amount`",
                    ),
                ],
            ),
            "",
            "## Mutual Action Plan",
            "",
            *_table(
                ("Milestone", "Our owner", "Their owner", "Exit condition"),
                [
                    (
                        f"Confirm scope at {account.stage_display}",
                        account.owner_id,
                        contacts[0].name if contacts else "to be named",
                        _stage_objective(account.stage),
                    ),
                    (
                        "Value working session",
                        account.owner_id,
                        next(
                            (item.name for item in contacts if item.rank == 0),
                            "economic buyer to be named",
                        ),
                        "Outcome measures agreed in the customer's own numbers",
                    ),
                    (
                        "Technical validation",
                        "solution engineering",
                        next(
                            (item.name for item in contacts if item.rank in {2, 3}),
                            "program owner to be named",
                        ),
                        "Success criteria signed off in writing",
                    ),
                    (
                        f"Advance to {next_code}",
                        account.owner_id,
                        contacts[0].name if contacts else "to be named",
                        next_objective,
                    ),
                ],
            ),
            "",
            "## Engagement Signals to Watch",
            "",
            *_bullets(
                (
                    "Which invitees actually open the room, and how many are new names.",
                    "Whether the value-case shelf is opened before the commercial shelf.",
                    "Whether anyone outside the known roster is forwarded access.",
                    "Time between publishing a milestone and the customer acting on it.",
                )
            ),
            "",
            "## Setup Checklist",
            "",
            *_numbered(
                (
                    "Create the room and set the owner to the account owner.",
                    "Publish only the shelves listed above; leave unmatched competitive "
                    "content out.",
                    "Invite every known contact individually so engagement is attributable.",
                    "Attach the mutual action plan and ask the customer to edit it directly.",
                    "Review engagement weekly and update the account activity date.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_positioning_deck(self, context: _AskContext) -> list[str]:
        """Outline a competitive deck and restate approved battlecards."""
        account = context.named_account
        intent = context.intent
        competitors = tuple(card.competitor_name for _, card in context.matched_cards)

        lines = [
            f"**Audience:** {account.name} — {account.industry}, "
            f"{account.employee_count:,} employees",
            f"**Competitors detected in the footprint:** "
            f"{_joined(competitors, 'none matched to an approved card')}",
            "",
            "## Deck Outline",
            "",
            *_table(
                ("Slide", "Title", "Content, grounded in"),
                [
                    (
                        "1",
                        "Where you are today",
                        f"Recorded footprint {account.products_display} and "
                        f"{account.employee_count:,} employees",
                    ),
                    (
                        "2",
                        "What we heard",
                        f"Recorded research topics: {intent.topics_display}"
                        if intent
                        else "Discovery notes; no intent signal on record",
                    ),
                    (
                        "3",
                        "The structural problem",
                        _joined(
                            tuple(
                                weakness
                                for _, card in context.matched_cards
                                for weakness in card.weaknesses[:1]
                            ),
                            "no approved weakness claims available",
                        ),
                    ),
                    (
                        "4",
                        "Our point of view",
                        _joined(
                            tuple(
                                card.value_hook
                                for _, card in context.matched_cards
                                if card.value_hook
                            ),
                            "no approved value hook available",
                        ),
                    ),
                    (
                        "5",
                        "How we are different",
                        "Kill points from the approved cards below",
                    ),
                    (
                        "6",
                        "Questions worth asking your own team",
                        "Approved trap questions, framed as self-assessment",
                    ),
                    (
                        "7",
                        "What good looks like",
                        f"The next stage objective: {_next_stage(account.stage)[1]}",
                    ),
                    (
                        "8",
                        "Proposed next step",
                        "One dated action, sized to the current stage",
                    ),
                ],
            ),
            "",
            *self._battlecard_sections(context),
            "",
            "## Delivery Guidance",
            "",
            *_bullets(
                (
                    "Present slide 3 as a question, not an accusation; the customer chose "
                    "the incumbent for reasons you have not heard yet.",
                    "Use only the weaknesses printed above. Anything else is unapproved.",
                    "Slide 6 works best if the customer answers out loud, so leave silence.",
                    f"Do not present commercial figures; this account's stage is "
                    f"{account.stage_display} and the value case is "
                    f"{'complete' if account.bva_complete else 'not complete'}.",
                )
            ),
            "",
            "## Battlecard Summary",
            "",
        ]
        if context.matched_cards:
            lines += _table(
                ("Competitor", "Value hook", "Weakness to probe", "Trap question"),
                [
                    (
                        card.competitor_name,
                        card.value_hook or "not recorded",
                        card.weaknesses[0] if card.weaknesses else "not recorded",
                        card.trap_questions[0] if card.trap_questions else "not recorded",
                    )
                    for _, card in context.matched_cards
                ],
            )
        else:
            lines.append(_unavailable("matched battlecard"))
        return lines

    # -- Renderers: negotiate -----------------------------------------------

    def _render_initial_quote(self, context: _AskContext) -> list[str]:
        """Structure a first quote from the recorded opportunity amount."""
        account = context.named_account
        economics = context.named_economics

        lines = [
            f"**Quote basis:** the recorded `open_opportunity_amount` of "
            f"{_money(account.open_opportunity_amount)}.",
            f"**Illustrative term:** {economics.term_months} months "
            f"({_money(economics.annualized_amount)} per year).",
            f"**Qualification state:** {economics.qualification_label} — stage "
            f"{economics.stage}, {account.stakeholder_count} stakeholder(s), BVA "
            f"{'complete' if account.bva_complete else 'incomplete'}.",
            "",
            "## Quote Structure",
            "",
            *_table(
                ("Line item", "Amount", "Share", "Basis"),
                [
                    (
                        label,
                        _money(amount),
                        f"{share:.0%}",
                        note,
                    )
                    for (label, amount, note), (_, share, _unused) in zip(
                        economics.components, _QUOTE_SPLIT, strict=True
                    )
                ],
            ),
            "",
            *_table(
                ("Total", "Amount"),
                [
                    ("List total for the term", _money(economics.open_amount)),
                    (
                        f"Maximum approved discount ({economics.approved_discount_pct}%)",
                        _money(round(economics.open_amount - economics.floor_amount, 2)),
                    ),
                    ("Floor at maximum approved discount", _money(economics.floor_amount)),
                ],
            ),
            "",
            "## Discount Guardrail",
            "",
            *_bullets(
                (
                    f"Approved without escalation: up to "
                    f"{economics.approved_discount_pct}%.",
                    f"Escalation approver beyond that: {economics.approval_owner}.",
                    f"The band is built from stage {economics.stage} (rank "
                    f"{economics.stage_rank}), BVA "
                    f"{'complete' if economics.bva_complete else 'incomplete'}, and "
                    f"{economics.stakeholder_count} engaged stakeholder(s).",
                )
            ),
            "",
            "## Readiness Before Sending",
            "",
            *_table(
                ("Gate", "State", "Action"),
                [
                    (
                        "Value case",
                        "Complete" if account.bva_complete else "Not complete",
                        "None"
                        if account.bva_complete
                        else "Do not lead with price; build the value case first",
                    ),
                    (
                        "Committee coverage",
                        f"{account.stakeholder_count} stakeholder(s)",
                        "None"
                        if account.stakeholder_count >= 3
                        else "Add stakeholders; a quote to one person rarely survives review",
                    ),
                    (
                        "Stage",
                        economics.stage,
                        "None"
                        if economics.stage_rank >= 40
                        else "Quoting before commercial stage invites early price anchoring",
                    ),
                    (
                        "Scope confirmation",
                        f"{account.employee_count:,} employees on record",
                        "Confirm the entitlement population with the customer",
                    ),
                ],
            ),
            "",
            "## Next Steps",
            "",
            *_numbered(
                (
                    "Confirm the entitlement population and term with the customer.",
                    "Send the quote to a named economic buyer, not a general address.",
                    "Attach the value case summary, or the agenda to build one.",
                    "Set a validity date and a review conversation before it lapses.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_proposal(self, context: _AskContext) -> list[str]:
        """Draft a proposal outline with a readiness gate."""
        account = context.named_account
        economics = context.named_economics
        intent = context.intent
        contacts = context.intel.contacts if context.intel else ()
        economic_buyer = next((item for item in contacts if item.rank == 0), None)

        gates: tuple[tuple[str, bool, str], ...] = (
            (
                "Business value assessment complete",
                account.bva_complete,
                "Run a value working session before proposing.",
            ),
            (
                "At least three engaged stakeholders",
                account.stakeholder_count >= 3,
                f"Only {account.stakeholder_count} engaged; multithread first.",
            ),
            (
                "Commercial stage reached (SS40 or later)",
                economics.stage_rank >= 40,
                f"Stage is {economics.stage}; confirm qualification first.",
            ),
            (
                "Economic buyer identified",
                economic_buyer is not None,
                "No chief-level contact on record; identify the buyer first.",
            ),
            (
                "Competitive position understood",
                bool(context.matched_cards),
                "No approved card matches the footprint; do not improvise.",
            ),
        )
        passed = sum(1 for _, met, _unused in gates if met)

        lines = [
            f"**Readiness:** {passed} of {len(gates)} gates met.",
            f"**Commercial reference:** {_money(account.open_opportunity_amount)} over "
            f"{economics.term_months} months.",
            "",
            "## Readiness Gate",
            "",
            *_table(
                ("Gate", "Met", "If not met"),
                [
                    (name, "Yes" if met else "No", "—" if met else remedy)
                    for name, met, remedy in gates
                ],
            ),
            "",
            (
                "All gates are met; proceed with the proposal below."
                if passed == len(gates)
                else "Close the open gates before sending. A proposal sent through an open "
                "gate usually returns as a discount request."
            ),
            "",
            "## Proposal Outline",
            "",
            "### 1. Executive summary",
            "",
            *_bullets(
                (
                    f"{account.name}, a {account.industry.lower()} organization of "
                    f"{account.employee_count:,} people, is working on "
                    + (
                        f"{intent.topics_display.lower()}."
                        if intent
                        else "identity access governance."
                    ),
                    f"The current footprint on record is {account.products_display}.",
                    "State the customer's own problem definition here, captured in "
                    "discovery, not a restatement of our capabilities.",
                )
            ),
            "",
            "### 2. Objectives and success measures",
            "",
            *_bullets(
                (
                    "Use the measures the customer confirmed in the value assessment."
                    if account.bva_complete
                    else "This section cannot be completed: no business value assessment is "
                    "recorded as complete.",
                    f"Recorded decision topics: {intent.topics_display}."
                    if intent
                    else "No recorded intent topics to anchor the objectives.",
                )
            ),
            "",
            "### 3. Proposed scope",
            "",
            *_table(
                ("Component", "Amount", "Scope note"),
                [(label, _money(amount), note) for label, amount, note in economics.components],
            ),
            "",
            "### 4. Commercial summary",
            "",
            *_bullets(
                (
                    f"Total for the term: {_money(economics.open_amount)}.",
                    f"Annualized: {_money(economics.annualized_amount)}.",
                    f"Discount approved without escalation: "
                    f"{economics.approved_discount_pct}%.",
                    f"Approver at this value: {economics.approval_owner}.",
                )
            ),
            "",
            "### 5. Mutual plan and signature path",
            "",
            *_table(
                ("Step", "Owner", "Condition to complete"),
                [
                    (
                        "Proposal review",
                        economic_buyer.name if economic_buyer else "economic buyer to be named",
                        "Buyer confirms scope and success measures",
                    ),
                    (
                        "Security and procurement review",
                        "customer procurement",
                        "Customer's own process steps confirmed",
                    ),
                    (
                        "Commercial approval",
                        economics.approval_owner,
                        f"Structure inside the {economics.approved_discount_pct}% guardrail",
                    ),
                    ("Signature", "both parties", "Countersigned agreement"),
                ],
            ),
            "",
            "### 6. What we are not claiming",
            "",
            *_bullets(
                (
                    "No savings percentage or payback period is asserted; this build holds no "
                    "benchmark data.",
                    "Competitive statements are limited to the approved cards matching "
                    f"{_joined(context.vendors, 'no recorded vendors')}.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_deal_risk(self, context: _AskContext) -> list[str]:
        """Report deal risk from a supplied assessment or derive it from the record."""
        account = context.named_account
        risk = context.risk

        lines: list[str] = []
        if risk is not None:
            lines += [
                f"**Risk level:** {risk.risk_level} ({risk.risk_score}/100)",
                f"**Summary:** {risk.summary}",
                "",
                "## Flags From the Supplied Assessment",
                "",
            ]
            if risk.flags:
                lines += _table(
                    ("Flag", "Severity", "Evidence", "Recommendation"),
                    [list(flag) for flag in risk.flags],
                )
            else:
                lines.append("No flags were reported by the supplied assessment.")
        else:
            lines += [
                "**Source:** no deal-risk assessment was supplied, so the indicators below "
                "are read directly from the account record.",
                "",
                "## Risk Indicators From the Account Record",
                "",
                *_table(
                    ("Indicator", "Value on record", "Reading"),
                    [
                        (
                            "Value case",
                            "Complete" if account.bva_complete else "Not complete",
                            "Healthy"
                            if account.bva_complete
                            else "High risk: the economic case is unproven",
                        ),
                        (
                            "Engaged stakeholders",
                            str(account.stakeholder_count),
                            "Healthy"
                            if account.stakeholder_count >= 3
                            else "Medium risk: coverage is thin"
                            if account.stakeholder_count == 2
                            else "High risk: single-threaded",
                        ),
                        (
                            "Days in stage",
                            str(account.days_in_stage),
                            "Healthy"
                            if account.days_in_stage <= 30
                            else "High risk: the stage has stalled",
                        ),
                        (
                            "Last activity",
                            account.last_activity_date,
                            "Confirm this reflects a real customer interaction",
                        ),
                        (
                            "Stage versus value",
                            f"{account.stage_display} at "
                            f"{_money(account.open_opportunity_amount)}",
                            "Healthy"
                            if _stage_rank(account.stage) >= 40
                            else "Watch: value is forecast from an early stage",
                        ),
                    ],
                ),
            ]

        lines += [
            "",
            "## Mitigation Plan",
            "",
            *_table(
                ("Risk", "Mitigation", "Owner", "By when"),
                [
                    (
                        gap,
                        action,
                        account.owner_id,
                        "This week" if index <= 2 else "Within two weeks",
                    )
                    for index, (gap, action) in enumerate(
                        zip(
                            self._gap_reasons(context) or ("No visible gaps",),
                            self._next_actions(context)
                            + ("Maintain the current plan and re-inspect weekly.",),
                            strict=False,
                        ),
                        start=1,
                    )
                ],
            ),
            "",
            "## Inspection Questions for the Forecast Call",
            "",
            *_numbered(
                (
                    "Who, by name, has told us they want this, and what did they say?",
                    f"What has changed in the {account.days_in_stage} days this deal has been "
                    f"in {account.stage_display}?",
                    "What is the customer's own next step, with a date they chose?",
                    f"Does {_money(account.open_opportunity_amount)} still reflect the scope "
                    "the customer described?",
                )
            ),
            "",
            *self._account_snapshot(account),
        ]
        return lines

    def _render_quote_discount_checker(self, context: _AskContext) -> list[str]:
        """Check a requested discount against the derived guardrail."""
        account = context.named_account
        economics = context.named_economics
        requested = context.requested_discount_pct

        lines = [
            f"**Approved without escalation:** up to "
            f"{economics.approved_discount_pct}% on {_money(economics.open_amount)}.",
            f"**Escalation approver:** {economics.approval_owner}.",
            "",
            "## How the Band Was Derived",
            "",
            *_table(
                ("Input", "Value on record", "Effect on the band"),
                [
                    ("Base allowance", "—", "8%"),
                    (
                        "BVA complete",
                        "Yes" if economics.bva_complete else "No",
                        "+4%" if economics.bva_complete else "no change",
                    ),
                    (
                        "Engaged stakeholders",
                        str(economics.stakeholder_count),
                        "+3%" if economics.stakeholder_count >= 3 else "no change",
                    ),
                    (
                        "Stage",
                        f"{economics.stage} (rank {economics.stage_rank})",
                        "+2%" if economics.stage_rank >= 40 else "no change",
                    ),
                    ("Cap", "—", "17% maximum"),
                    (
                        "Result",
                        f"{economics.qualification_label}",
                        f"{economics.approved_discount_pct}%",
                    ),
                ],
            ),
            "",
            "## Verdict",
            "",
        ]
        if requested is None:
            lines += [
                "No discount was supplied to check. Pass `requested_discount_pct`, or state "
                "the figure in the request, for example “can I approve 22% off?”.",
                "",
                *_table(
                    ("Requested", "Outcome", "Net amount"),
                    [
                        (
                            f"{percent}%",
                            "Approved at your level"
                            if percent <= economics.approved_discount_pct
                            else f"Escalate to {economics.approval_owner}",
                            _money(round(economics.open_amount * (1 - percent / 100), 2)),
                        )
                        for percent in (5, 10, 15, 20, 25, 30)
                    ],
                ),
                "",
                "_The table above is a reference grid, not an approval._",
            ]
        else:
            net = round(economics.open_amount * (1 - requested / 100), 2)
            give_up = round(economics.open_amount - net, 2)
            if requested <= economics.approved_discount_pct:
                verdict = "**Approved at your level.**"
                action = (
                    "You can proceed without escalation. Record the justification on the "
                    "opportunity anyway."
                )
            elif requested <= economics.approved_discount_pct + 10:
                verdict = f"**Escalation required to {economics.approval_owner}.**"
                action = (
                    "Prepare the justification below before requesting approval; the request "
                    "will be judged on qualification evidence, not urgency."
                )
            else:
                verdict = "**Blocked pending deal desk review.**"
                action = (
                    "This exceeds the guardrail by more than ten points. Deal desk review is "
                    "required, and a discount of this size usually signals a qualification "
                    "problem rather than a pricing problem."
                )
            lines += [
                f"Requested discount: **{requested:g}%** against an approved band of "
                f"**{economics.approved_discount_pct}%**.",
                "",
                verdict,
                "",
                *_table(
                    ("Measure", "Value"),
                    [
                        ("List total for the term", _money(economics.open_amount)),
                        (f"Discount at {requested:g}%", _money(give_up)),
                        ("Net to the customer", _money(net)),
                        (
                            "Gap to the approved band",
                            f"{max(0.0, requested - economics.approved_discount_pct):g} "
                            "percentage points",
                        ),
                        ("Approver required", economics.approval_owner),
                    ],
                ),
                "",
                action,
            ]

        lines += [
            "",
            "## Justification Checklist",
            "",
            *_table(
                ("Requirement", "State on record"),
                [
                    (
                        "Completed business value assessment",
                        "Present" if account.bva_complete else "Missing",
                    ),
                    (
                        "Three or more engaged stakeholders",
                        "Met" if account.stakeholder_count >= 3 else
                        f"Not met ({account.stakeholder_count})",
                    ),
                    (
                        "Commercial stage reached",
                        "Met" if economics.stage_rank >= 40 else f"Not met ({economics.stage})",
                    ),
                    (
                        "Competitive pressure documented",
                        _joined(
                            tuple(card.competitor_name for _, card in context.matched_cards),
                            "no matched battlecard",
                        ),
                    ),
                    (
                        "Scope confirmed with the customer",
                        f"{account.employee_count:,} employees on record; confirm entitlement",
                    ),
                ],
            ),
            "",
            "## Alternatives to Giving Discount",
            "",
            *_bullets(
                (
                    "Trade term length for rate rather than reducing rate outright.",
                    "Reduce scope to match the confirmed population instead of discounting "
                    "the full population.",
                    "Trade the discount for a reference commitment or a joint success review.",
                    "Close the qualification gaps above; most discount requests are "
                    "qualification problems wearing a pricing costume.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_contract_review(self, context: _AskContext) -> list[str]:
        """Review contract structure against the account record."""
        account = context.named_account
        economics = context.named_economics

        lines = [
            f"**Agreement value on record:** {_money(account.open_opportunity_amount)} over "
            f"{economics.term_months} months.",
            f"**Entitlement basis to confirm:** {account.employee_count:,} employees "
            f"recorded on the account.",
            "",
            "## Review Checklist",
            "",
            *_table(
                ("Clause area", "What to verify", "Grounded in"),
                [
                    (
                        "Term and renewal",
                        f"The {economics.term_months}-month illustrative term matches what "
                        "the customer agreed, and the renewal notice window is workable",
                        "Local demo term convention",
                    ),
                    (
                        "Entitlement basis",
                        f"The metric matches the {account.employee_count:,} employee "
                        "population, and states what happens as that number changes",
                        "Account `employee_count`",
                    ),
                    (
                        "True-up mechanics",
                        "How growth above the entitlement is measured, priced, and when it "
                        "is trued up",
                        f"Account `employee_count` of {account.employee_count:,}",
                    ),
                    (
                        "Commercial terms",
                        f"Total, payment schedule, and that any discount stays within the "
                        f"{economics.approved_discount_pct}% approved band",
                        "Account `open_opportunity_amount`, `stage`, `bva_complete`, "
                        "`stakeholder_count`",
                    ),
                    (
                        "Displacement and transition",
                        "Any commitments related to the recorded incumbent footprint: "
                        f"{account.products_display}",
                        "Account `current_products`",
                    ),
                    (
                        "Data protection and industry terms",
                        f"Requirements specific to {account.industry} are addressed by the "
                        "customer's own regulatory obligations",
                        "Account `industry`",
                    ),
                    (
                        "Services scope",
                        f"The {_money(economics.components[-1][1])} services component has a "
                        "defined deliverable and completion definition",
                        "Derived services component",
                    ),
                    (
                        "Signature authority",
                        f"The signer has authority at this value; {economics.approval_owner} "
                        "approves on our side",
                        "Derived approval tier",
                    ),
                ],
            ),
            "",
            "## Commercial Terms as Structured",
            "",
            *_table(
                ("Component", "Amount", "Note"),
                [(label, _money(amount), note) for label, amount, note in economics.components],
            ),
            "",
            "## Risk Flags in the Current Record",
            "",
            *_bullets(
                (
                    f"Qualification state is {economics.qualification_label}; contracts signed "
                    "from a thin base renew badly.",
                    "No completed business value assessment is recorded, so there are no "
                    "agreed success measures to reference in the agreement."
                    if not account.bva_complete
                    else "The completed value case should be referenced so renewal is measured "
                    "against agreed outcomes.",
                    f"Only {account.stakeholder_count} stakeholder(s) are engaged; confirm the "
                    "signer is not the only person invested."
                    if account.stakeholder_count < 3
                    else f"{account.stakeholder_count} stakeholders are engaged, which supports "
                    "a durable agreement.",
                    f"Stage is {economics.stage}; verify that paper is not moving ahead of "
                    "validation."
                    if economics.stage_rank < 40
                    else f"Stage {economics.stage} is consistent with paper being in motion.",
                )
            ),
            "",
            "## Escalation Path",
            "",
            *_numbered(
                (
                    f"Commercial deviation: {economics.approval_owner}.",
                    "Legal language changes: deal desk, then legal review.",
                    "Security or data-protection changes: security review before signature.",
                    "Anything outside the approved discount band: deal desk review with the "
                    "justification checklist attached.",
                )
            ),
            "",
            "_This is a commercial readiness review, not legal advice. Legal review is a "
            "separate, required step._",
            "",
            _DEMO_NOTE,
        ]
        return lines

    # -- Renderers: post-sale and enablement --------------------------------

    def _render_post_sales_handoff(self, context: _AskContext) -> list[str]:
        """Assemble the post-sales handoff packet."""
        account = context.named_account
        economics = context.named_economics
        intent = context.intent
        contacts = context.intel.contacts if context.intel else ()

        lines = [
            f"**Handing off:** {account.name} (`{account.account_id}`, {account.domain})",
            f"**From:** {account.owner_id} · **Territory:** {account.territory} · "
            f"**Tier:** {account.target_tier}",
            f"**Contracted reference:** {_money(account.open_opportunity_amount)} over "
            f"{economics.term_months} months.",
            "",
            "## Purchased Scope",
            "",
            *_table(
                ("Component", "Amount", "What delivery owns"),
                [(label, _money(amount), note) for label, amount, note in economics.components],
            ),
            "",
            f"Entitlement population to verify at onboarding: "
            f"{account.employee_count:,} employees.",
            "",
            "## Stakeholder Roster",
            "",
        ]
        if contacts:
            lines += _table(
                ("Contact", "Title", "Department", "Email", "Handoff role"),
                [
                    (
                        contact.name,
                        contact.title,
                        contact.department,
                        contact.email,
                        {
                            0: "Executive sponsor for the program",
                            1: "Program owner and escalation point",
                            2: "Day-to-day project lead",
                            3: "Operational owner",
                            4: "Informed stakeholder",
                        }[contact.rank],
                    )
                    for contact in contacts
                ],
            )
        else:
            lines.append(
                _unavailable("contact roster, so the roster must be rebuilt before kickoff")
            )

        lines += [
            "",
            "## Success Criteria",
            "",
            *_bullets(
                (
                    "Carry the agreed outcome measures from the completed business value "
                    "assessment into the delivery plan."
                    if account.bva_complete
                    else "**Gap:** no completed business value assessment is recorded, so "
                    "there are no agreed success measures to hand over. Establish them in "
                    "the first delivery session.",
                    f"Recorded customer priorities to honour: "
                    f"{intent.topics_display if intent else 'none recorded'}.",
                    f"Incumbent footprint delivery must work alongside: "
                    f"{account.products_display}.",
                )
            ),
            "",
            "## Onboarding Milestones",
            "",
            *_table(
                ("Milestone", "Owner", "Exit condition"),
                [
                    (
                        "Kickoff and roster confirmation",
                        "customer success",
                        "Every role above confirmed or replaced by a named person",
                    ),
                    (
                        "Entitlement verification",
                        "delivery",
                        f"Actual population reconciled against {account.employee_count:,}",
                    ),
                    (
                        "First value milestone",
                        "delivery with the program owner",
                        "One agreed success measure showing movement",
                    ),
                    (
                        "Executive review",
                        "account owner with customer success",
                        "Sponsor confirms the program is on track",
                    ),
                ],
            ),
            "",
            "## Open Risks Carried Into Delivery",
            "",
            *_bullets(
                self._gap_reasons(context)
                or ("No open qualification risks are visible in the record.",)
            ),
            "",
            "## Continuing Commercial Context",
            "",
            *_bullets(
                (
                    f"Expansion motion suggested by the record: "
                    f"{self._upsell_score(account, intent).motion}.",
                    f"True-up exposure tracks the {account.employee_count:,} employee "
                    "population; verify growth at each review.",
                    f"Account owner {account.owner_id} retains commercial ownership; "
                    "customer success owns adoption.",
                )
            ),
            "",
            _DEMO_NOTE,
        ]
        return lines

    def _render_rules_of_engagement(self, context: _AskContext) -> list[str]:
        """Explain the demo rules of engagement, with account context when available."""
        lines = [
            "This is the bundled sample rules-of-engagement summary for this local build.",
            "",
            _DEMO_NOTE,
            "",
        ]
        if context.account is not None:
            account = context.account
            lines += [
                "## Context From the Selected Account",
                "",
                *_table(
                    ("Field", "Value"),
                    [
                        ("Account", f"{account.name} (`{account.account_id}`)"),
                        ("Recorded owner", account.owner_id),
                        ("Territory", account.territory),
                        ("Target tier", account.target_tier),
                        ("Stage", account.stage_display),
                        ("Open opportunity", _money(account.open_opportunity_amount)),
                    ],
                ),
                "",
                f"The record shows **{account.owner_id}** as the owner of "
                f"**{account.name}** in **{account.territory}**. Ownership questions are "
                "settled by the `owner_id` and `territory` fields on the account, not by "
                "who spoke to the customer most recently.",
                "",
            ]
        else:
            lines += [
                "No account was supplied, so the guidance below is generic. Pass an "
                "`account` to see the recorded owner and territory for a specific case.",
                "",
            ]

        lines += [
            "## Demo Rules of Engagement",
            "",
            "### Account ownership",
            "",
            *_bullets(
                (
                    "The `owner_id` on the account record is the single source of truth for "
                    "ownership.",
                    "Ownership follows the account, not the opportunity, and not the contact "
                    "who replied first.",
                    "Ownership changes are made on the record before any customer contact "
                    "changes hands.",
                )
            ),
            "",
            "### Territory assignment and splits",
            "",
            *_bullets(
                (
                    "The `territory` field determines coverage; in this build the values are "
                    "geographic codes such as `US-WEST`.",
                    "Where a customer spans territories, the territory on the account record "
                    "governs credit and the two owners agree a joint plan in writing.",
                    "Target tier (`target_tier`) determines coverage intensity, not "
                    "ownership.",
                )
            ),
            "",
            "### Overlay and specialist engagement",
            "",
            *_bullets(
                (
                    "Overlay specialists engage at the account owner's request and do not "
                    "carry independent ownership.",
                    "Solution engineering engages once qualification is recorded, so effort "
                    "follows evidence.",
                    "Deal desk engages when commercial terms fall outside the approved "
                    "discount band.",
                )
            ),
            "",
            "### Opportunity registration and conflicts",
            "",
            *_bullets(
                (
                    "Register the opportunity on the owning account before pursuing it, so "
                    "the `stage` and `open_opportunity_amount` fields stay authoritative.",
                    "Two sellers pursuing the same account is resolved by the record, then "
                    "by the shared manager, in that order.",
                    "Partner-originated deals are registered against the same account "
                    "record so a single view of stage and value exists.",
                )
            ),
            "",
            "### Escalation",
            "",
            *_numbered(
                (
                    "Raise it with the other account owner directly, referencing the record.",
                    "If unresolved, escalate to the shared first-line manager.",
                    "If still unresolved, escalate to the regional leader with the account "
                    "record attached.",
                    "Escalations are decided on recorded facts, not on narrative.",
                )
            ),
            "",
            "## What This Build Cannot Tell You",
            "",
            *_bullets(
                (
                    "It holds no company policy document, so treat every rule above as sample "
                    "guidance.",
                    "It holds no partner, overlay, or compensation-plan records.",
                    "For a binding answer, consult the published policy for your region.",
                )
            ),
        ]
        return lines

    def _render_commission_plans(self, context: _AskContext) -> list[str]:
        """Explain the demo commission structure and show an illustrative payout."""
        lines = [
            "This is the bundled sample commission explanation for this local build.",
            "",
            _DEMO_NOTE,
            "",
            "## Demo Plan Structure",
            "",
            *_table(
                ("Element", "Sample treatment"),
                [
                    (
                        "Plan shape",
                        "Base salary plus variable, split annually with quarterly "
                        "measurement",
                    ),
                    ("Quota basis", "Annual bookings target, measured on closed-won value"),
                    ("Rate to quota", "A flat rate applies up to 100% of quota"),
                    ("Accelerator", "An increased rate applies to bookings above 100% of quota"),
                    ("Measurement", "Quarterly, with annual true-up at the end of the plan year"),
                    ("Payment timing", "Following the month in which the booking is recognized"),
                ],
            ),
            "",
            "## Credit Rules by Motion",
            "",
            *_table(
                ("Motion", "Sample credit treatment", "What the record must show"),
                [
                    (
                        "New business",
                        "Full quota credit to the account owner",
                        "`owner_id` on the account and a closed-won stage",
                    ),
                    (
                        "Upsell",
                        "Full credit on the incremental value only",
                        "Prior footprint in `current_products` and an incremental amount",
                    ),
                    (
                        "Cross-sell",
                        "Full credit on the new scope",
                        "New scope distinct from `current_products`",
                    ),
                    (
                        "True-up",
                        "Credit on the incremental entitlement value",
                        "Growth against the contracted population",
                    ),
                    (
                        "Renewal",
                        "Reduced rate, since retention is a different motion",
                        "An existing agreement being extended",
                    ),
                ],
            ),
            "",
            "## Illustrative Payout Calculation",
            "",
        ]
        if context.account is not None:
            account = context.account
            economics = context.named_economics
            base_rate = 0.08
            accelerated_rate = 0.12
            base_payout = round(account.open_opportunity_amount * base_rate, 2)
            accelerated_payout = round(account.open_opportunity_amount * accelerated_rate, 2)
            lines += [
                f"Using the recorded open opportunity amount for **{account.name}** as the "
                "booking value:",
                "",
                *_table(
                    ("Input", "Value"),
                    [
                        ("Booking value used", _money(account.open_opportunity_amount)),
                        ("Recorded stage", economics.stage),
                        (
                            "Motion implied by the record",
                            self._upsell_score(account, context.intent).motion,
                        ),
                        ("Sample rate below quota", f"{base_rate:.0%}"),
                        ("Sample accelerated rate", f"{accelerated_rate:.0%}"),
                        ("Payout at the sample base rate", _money(base_payout)),
                        (
                            "Payout at the sample accelerated rate",
                            _money(accelerated_payout),
                        ),
                    ],
                ),
                "",
                "_The rates are sample figures from this local build. The booking value is "
                "the account's recorded `open_opportunity_amount`, which is an open "
                "opportunity, not a closed booking._",
            ]
        else:
            lines += [
                "No account was supplied, so there is no booking value to calculate against. "
                "Pass an `account` to see an illustrative calculation using its recorded "
                "`open_opportunity_amount`.",
            ]

        lines += [
            "",
            "## Common Questions",
            "",
            *_table(
                ("Question", "Sample answer"),
                [
                    (
                        "When is a deal credited?",
                        "When the booking is recognized, which follows signature and not "
                        "verbal agreement",
                    ),
                    (
                        "What happens if an account changes owner mid-cycle?",
                        "Credit follows the recorded `owner_id` at the time of booking, with "
                        "any split agreed in writing beforehand",
                    ),
                    (
                        "Does a discount reduce my credit?",
                        "Yes, credit is calculated on the net booking value, which is why "
                        "the discount band matters",
                    ),
                    (
                        "Are services credited the same as subscription?",
                        "In this sample plan services carry a lower rate than subscription",
                    ),
                ],
            ),
            "",
            "## What This Build Cannot Tell You",
            "",
            *_bullets(
                (
                    "Your actual quota, rates, accelerators, or plan year.",
                    "Any personal earnings, attainment, or payment history.",
                    "Regional plan variations or in-quarter incentive programs.",
                    "For a binding answer, consult your signed compensation plan.",
                )
            ),
        ]
        return lines

    def _render_product_overview(self, context: _AskContext) -> list[str]:
        """Summarize demo capability areas and map recorded intent topics onto them."""
        lines = [
            "This is the bundled sample product framing for this local build.",
            "",
            _DEMO_NOTE,
            "",
            "## Capability Areas",
            "",
            *_table(
                ("Capability area", "What it addresses"),
                [(name, description) for name, description in _DEMO_CAPABILITY_AREAS],
            ),
            "",
        ]

        topics = tuple(
            dict.fromkeys(
                topic
                for signal in (
                    [context.intent] if context.intent else list(context.signals.values())
                )
                if signal is not None
                for topic in signal.intent_topics
            )
        )
        lines += ["## Recorded Customer Topics Mapped to Capability Areas", ""]
        if topics:
            rows: list[tuple[str, str]] = []
            for topic in topics:
                topic_words = {
                    word for word in _pad(topic).split() if len(word) > 3
                }
                matches = [
                    name
                    for name, _description in _DEMO_CAPABILITY_AREAS
                    if topic_words & {word for word in _pad(name).split() if len(word) > 3}
                ]
                rows.append(
                    (
                        topic,
                        _joined(
                            tuple(matches),
                            "no mapped capability area; treat this topic as discovery input",
                        ),
                    )
                )
            lines += _table(("Recorded topic", "Mapped capability area"), rows)
            lines += [
                "",
                "_Topics are read from the supplied intent signals. The mapping is a word "
                "overlap against the sample capability names, not a product claim._",
            ]
        else:
            lines.append(
                "No intent signals were supplied, so there are no recorded customer topics "
                "to map. Pass `intent` or `signals` to ground this overview."
            )

        if context.vendors:
            lines += [
                "",
                "## Vendors on Record and Approved Guidance",
                "",
                *_table(
                    ("Vendor on record", "Approved card", "Approved value hook"),
                    [
                        (
                            vendor,
                            card.competitor_name,
                            card.value_hook or "not recorded",
                        )
                        for vendor, card in context.matched_cards
                    ]
                    or [
                        (vendor, "none matched", "make no competitive claim")
                        for vendor in context.vendors
                    ],
                ),
            ]

        lines += [
            "",
            "## How to Use This",
            "",
            *_bullets(
                (
                    "Use the capability areas as conversation structure, not as a feature "
                    "list to read aloud.",
                    "Lead with the customer's recorded topic and connect it to one area.",
                    "Make no claim about outcomes, savings, or timelines; this build holds no "
                    "benchmark or roadmap data.",
                    "For approved competitive language, use the battlecard sections rather "
                    "than this overview.",
                )
            ),
            "",
            "## What This Build Cannot Tell You",
            "",
            *_bullets(
                (
                    "Current product names, packaging, editions, or pricing.",
                    "Roadmap, release dates, or supported integrations.",
                    "Certifications, compliance attestations, or reference customers.",
                )
            ),
        ]
        return lines
