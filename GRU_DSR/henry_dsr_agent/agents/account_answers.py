"""Direct answers to factual questions sellers ask about an account.

The Ask catalog renders long, structured deliverables such as an account plan or a
proposal. Sellers also ask short questions -- "what stage is this account in?",
"who should I call?", "what tasks are left?" -- that deserve a two-line answer
rather than a document. :class:`AccountQuestionAgent` recognises those questions
and answers them from the same local records the catalog uses.

The agent is deliberately conservative: it only claims a question when the text
reads like one *and* names a topic it can answer from the supplied records. Every
other request is left to the Ask catalog and the workflow graphs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Final

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
)
from .dsr_ask_catalog import next_stage, stage_objective

__all__ = [
    "AccountAnswer",
    "AccountQuestion",
    "AccountQuestionAgent",
    "AccountQuestionTopic",
]


class AccountQuestionTopic(str, Enum):
    """A question subject the agent can answer from local records."""

    STAGE = "stage"
    DEAL_VALUE = "deal_value"
    OWNERSHIP = "ownership"
    ACTIVITY = "activity"
    COMPANY_PROFILE = "company_profile"
    TECHNOLOGY = "technology"
    INTENT = "intent"
    CONTACTS = "contacts"
    RISK = "risk"
    TASKS = "tasks"
    OVERVIEW = "overview"


class AccountQuestion(BaseModel):
    """Explainable outcome of recognising a seller question."""

    topic: AccountQuestionTopic
    matched_phrase: str
    confidence: float = Field(ge=0.0, le=1.0)


class AccountAnswer(BaseModel):
    """A short, sourced answer to one account question."""

    topic: AccountQuestionTopic
    markdown: str = Field(min_length=1)
    account_name: str | None = None
    needs_account_selection: bool = False
    data_sources: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Question recognition
# ---------------------------------------------------------------------------

# Openers that make a sentence a request for information rather than a command
# to produce a deliverable. "Draft an email about the stage" is not a question;
# "what is the stage" is.
_QUESTION_OPENERS: Final[frozenset[str]] = frozenset(
    {
        "am", "any", "are", "brief", "can", "catch", "could", "did", "do", "does",
        "has", "have", "how", "is", "list", "remind", "should", "show", "summarise",
        "summarize", "tell", "was", "were", "what", "whats", "when", "where",
        "which", "who", "whos", "whose", "why", "will",
    }
)

# (topic, phrases). The longest matching phrase wins, then declaration order.
_TOPIC_PHRASES: Final[tuple[tuple[AccountQuestionTopic, tuple[str, ...]], ...]] = (
    (
        AccountQuestionTopic.TASKS,
        (
            "task", "tasks", "to do", "to dos", "todo", "todos", "action item",
            "action items", "checklist", "left to do", "still open", "outstanding",
        ),
    ),
    (
        AccountQuestionTopic.STAGE,
        (
            "stage", "sales stage", "deal stage", "pipeline stage", "days in stage",
            "how far along", "where is this deal", "where are we",
        ),
    ),
    (
        AccountQuestionTopic.INTENT,
        (
            "intent", "intent score", "intent topics", "buying stage", "in market",
            "in the market", "how hot", "6sense", "profile fit", "surging",
        ),
    ),
    (
        AccountQuestionTopic.RISK,
        (
            "risk", "risks", "risky", "at risk", "deal health", "red flag",
            "red flags", "blockers", "what could go wrong",
        ),
    ),
    (
        AccountQuestionTopic.CONTACTS,
        (
            "contact", "contacts", "key contacts", "decision maker", "decision makers",
            "who should i call", "who should i contact", "who should i email",
            "buying committee", "champion", "stakeholders", "who do we know",
        ),
    ),
    (
        AccountQuestionTopic.OWNERSHIP,
        (
            "owner", "who owns", "account owner", "rep", "assigned", "territory",
            "region", "tier",
        ),
    ),
    (
        AccountQuestionTopic.TECHNOLOGY,
        (
            "tech", "technology", "technologies", "tech stack", "stack", "products",
            "current products", "installed", "vendors", "competitor", "competitors",
            "incumbent", "what do they use", "what are they using",
        ),
    ),
    (
        AccountQuestionTopic.DEAL_VALUE,
        (
            "deal size", "deal value", "opportunity amount", "open opportunity",
            "how much", "how big is the deal", "amount", "acv", "arr", "worth",
            "bva", "business value assessment",
        ),
    ),
    (
        AccountQuestionTopic.ACTIVITY,
        (
            "last activity", "last touch", "last touched", "last contact",
            "last contacted", "how long since", "when did we last", "stale",
            "recent activity",
        ),
    ),
    (
        AccountQuestionTopic.COMPANY_PROFILE,
        (
            "industry", "employees", "employee count", "headcount", "annual revenue",
            "revenue", "company size", "how big is", "vertical", "domain", "website",
        ),
    ),
    (
        AccountQuestionTopic.OVERVIEW,
        (
            "overview", "summary", "summarise", "summarize", "tell me about",
            "what do we know", "who are they", "brief me", "catch me up",
        ),
    ),
)

_TOPICS_NEEDING_ACCOUNT: Final[frozenset[AccountQuestionTopic]] = frozenset(
    topic for topic in AccountQuestionTopic if topic is not AccountQuestionTopic.TASKS
)


def _normalize(text: str) -> str:
    """Fold ``text`` to space-padded lowercase words so phrases match on edges."""
    folded = "".join(character if character.isalnum() else " " for character in text.lower())
    return f" {' '.join(folded.split())} "


_PHRASE_INDEX: Final[tuple[tuple[str, str, AccountQuestionTopic, int], ...]] = tuple(
    (_normalize(phrase), phrase, topic, order)
    for order, (topic, phrases) in enumerate(_TOPIC_PHRASES)
    for phrase in phrases
)


# ---------------------------------------------------------------------------
# Record readers
# ---------------------------------------------------------------------------


def _iso_date(source: Any, *names: str) -> str:
    """Read a date-like field and render it in ISO-8601 form."""
    raw = text_value(source, *names)
    return raw[:10] if raw else ""


def _days_since(iso_day: str, *, as_of: date | None = None) -> int | None:
    """Return whole days between ``iso_day`` and today, or ``None`` when unparsable."""
    if not iso_day:
        return None
    try:
        parsed = date.fromisoformat(iso_day[:10])
    except ValueError:
        return None
    today = as_of or datetime.now(timezone.utc).date()
    return max(0, (today - parsed).days)


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    """Render ``count`` with the matching noun form."""
    return f"{count} {singular if count == 1 else (plural or f'{singular}s')}"


@dataclass(frozen=True)
class _Tasks:
    """One account's task list as the browser recorded it."""

    account_id: str
    account_name: str
    open_items: tuple[str, ...]
    done_items: tuple[str, ...]

    @property
    def total(self) -> int:
        return len(self.open_items) + len(self.done_items)

    @classmethod
    def from_object(cls, board_entry: Any) -> _Tasks:
        """Read one ``{account_id, account_name, items: [...]}`` board entry."""
        open_items: list[str] = []
        done_items: list[str] = []
        for item in items_value(board_entry, "items", "tasks"):
            text = text_value(item, "text", "title", "label")
            if not text:
                continue
            (done_items if bool_value(item, "done", "complete") else open_items).append(text)
        return cls(
            account_id=text_value(board_entry, "account_id", "id"),
            account_name=text_value(board_entry, "account_name", "name", default="this account"),
            open_items=tuple(open_items),
            done_items=tuple(done_items),
        )


@dataclass(frozen=True)
class _Snapshot:
    """Everything an answer may read, extracted once from the supplied records."""

    account: Any
    intent: Any
    intel: Any
    risk: Any
    tasks: _Tasks | None
    board: tuple[_Tasks, ...]

    @property
    def name(self) -> str:
        return text_value(self.account, "name", default="This account")

    @property
    def stage(self) -> str:
        return text_value(self.account, "stage")

    @property
    def domain(self) -> str:
        return text_value(self.account, "domain")

    @property
    def days_in_stage(self) -> int:
        return int_value(self.account, "days_in_stage")

    @property
    def stakeholder_count(self) -> int:
        return int_value(self.account, "stakeholder_count")

    @property
    def bva_display(self) -> str:
        return "complete" if bool_value(self.account, "bva_complete") else "not complete"

    @property
    def products(self) -> tuple[str, ...]:
        return string_values(self.account, "current_products")

    @property
    def intel_source(self) -> str:
        return text_value(self.intel, "source", default="ZoomInfo")

    def field(self, *names: str, default: str = "not recorded") -> str:
        return text_value(self.account, *names, default=default)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class AccountQuestionAgent(BaseAgent[AccountAnswer]):
    """Recognise and answer short factual questions about one account.

    Example::

        agent = AccountQuestionAgent()
        question = agent.classify("what stage is this account in?")
        answer = await agent.run(question, account=account)
    """

    def classify(self, message: str) -> AccountQuestion | None:
        """Return the question ``message`` asks, or ``None`` when it is not one.

        A message qualifies when it opens with an interrogative or ends in a
        question mark *and* mentions a topic the agent can answer. Anything else
        is left for the Ask catalog so that deliverable requests still render
        their full documents.
        """
        text = message.strip()
        if not text:
            return None
        normalized = _normalize(text)
        opener = normalized.split(" ", 2)[1] if len(normalized) > 2 else ""
        if not text.endswith("?") and opener not in _QUESTION_OPENERS:
            return None

        matches = sorted(
            (-len(padded), order, phrase, topic)
            for padded, phrase, topic, order in _PHRASE_INDEX
            if padded in normalized
        )
        if not matches:
            return None
        _, _, phrase, topic = matches[0]
        return AccountQuestion(
            topic=topic,
            matched_phrase=phrase,
            confidence=round(min(1.0, 0.6 + len(phrase) / 60), 2),
        )

    async def run(
        self,
        question: AccountQuestion,
        *,
        account: Any | None = None,
        intent: Any | None = None,
        technographics: Any | None = None,
        deal_risk: Any | None = None,
        task_board: Sequence[Any] | None = None,
        **_: Any,
    ) -> AccountAnswer:
        """Answer ``question`` from the supplied records.

        Args:
            question: The recognised question, from :meth:`classify`.
            account: Focus account record (``SalesforceAccount``-shaped).
            intent: Intent signal for the focus account, when one exists.
            technographics: ZoomInfo-shaped technology and contact record.
            deal_risk: A previously computed deal-risk assessment.
            task_board: Per-account task lists owned by the browser client.

        Returns:
            An :class:`AccountAnswer`. When the topic needs an account that was
            not supplied, the answer explains how to pick one instead of guessing.
        """
        board = tuple(_Tasks.from_object(entry) for entry in (task_board or ()))
        account_id = text_value(account, "id", "account_id")
        tasks = next((entry for entry in board if entry.account_id == account_id), None)
        snapshot = _Snapshot(
            account=account,
            intent=intent,
            intel=technographics,
            risk=deal_risk,
            tasks=tasks,
            board=board,
        )

        if account is None and question.topic in _TOPICS_NEEDING_ACCOUNT:
            return AccountAnswer(
                topic=question.topic,
                markdown=self._account_prompt(question),
                needs_account_selection=True,
            )

        renderers = {
            AccountQuestionTopic.STAGE: self._answer_stage,
            AccountQuestionTopic.DEAL_VALUE: self._answer_deal_value,
            AccountQuestionTopic.OWNERSHIP: self._answer_ownership,
            AccountQuestionTopic.ACTIVITY: self._answer_activity,
            AccountQuestionTopic.COMPANY_PROFILE: self._answer_company_profile,
            AccountQuestionTopic.TECHNOLOGY: self._answer_technology,
            AccountQuestionTopic.INTENT: self._answer_intent,
            AccountQuestionTopic.CONTACTS: self._answer_contacts,
            AccountQuestionTopic.RISK: self._answer_risk,
            AccountQuestionTopic.TASKS: self._answer_tasks,
            AccountQuestionTopic.OVERVIEW: self._answer_overview,
        }
        lines = renderers[question.topic](snapshot)
        return AccountAnswer(
            topic=question.topic,
            markdown="\n".join(lines).strip() + "\n",
            account_name=snapshot.name if account is not None else None,
            data_sources=self._data_sources(question.topic, snapshot),
        )

    # -- Answer bodies ------------------------------------------------------

    @staticmethod
    def _account_prompt(question: AccountQuestion) -> str:
        """Explain how to name an account instead of guessing at one."""
        return (
            f"**I need an account before I can answer that.** You asked about "
            f"*{question.matched_phrase}*, which I read from one account's records.\n\n"
            "- Name it in the question, for example "
            "*“what stage is Apex Financial in?”*\n"
            "- Or pick an account in **Accounts & tasks** and ask again.\n"
        )

    def _answer_stage(self, snapshot: _Snapshot) -> list[str]:
        stage = snapshot.stage
        if not stage:
            return [
                f"**{snapshot.name} has no sales stage recorded in Salesforce.**",
                "",
                "- Qualify the opportunity and set a stage before forecasting it.",
                self._source(snapshot, "Salesforce account record"),
            ]
        days = int_value(snapshot.account, "days_in_stage")
        upcoming_code, upcoming_objective = next_stage(stage)
        amount = number_value(snapshot.account, "open_opportunity_amount")
        return [
            f"**{snapshot.name} is at stage {stage}** — "
            f"{stage_objective(stage).lower()}.",
            "",
            f"- **{_plural(days, 'day')} in stage** as recorded on the account.",
            f"- Next stage is **{upcoming_code}** — {upcoming_objective.lower()}.",
            f"- Open opportunity: **{format_money(amount)}**.",
            f"- Business value assessment: **{snapshot.bva_display}**.",
            self._source(snapshot, "Salesforce account record"),
        ]

    def _answer_deal_value(self, snapshot: _Snapshot) -> list[str]:
        amount = number_value(snapshot.account, "open_opportunity_amount")
        stage = snapshot.stage or "no recorded stage"
        headline = (
            f"**{snapshot.name} has {format_money(amount)} in open opportunity.**"
            if amount
            else f"**{snapshot.name} has no open opportunity amount recorded.**"
        )
        return [
            headline,
            "",
            f"- Stage **{stage}**, {_plural(snapshot.days_in_stage, 'day')} in stage.",
            f"- Business value assessment: **{snapshot.bva_display}**.",
            f"- Engaged stakeholders on the record: **{snapshot.stakeholder_count}**.",
            self._source(snapshot, "Salesforce account record"),
        ]

    def _answer_ownership(self, snapshot: _Snapshot) -> list[str]:
        return [
            f"**{snapshot.field('owner_id', 'account_owner')} owns {snapshot.name}.**",
            "",
            f"- Territory: **{snapshot.field('territory')}**.",
            f"- Target tier: **{snapshot.field('target_tier')}**.",
            f"- Industry: **{snapshot.field('industry')}**.",
            self._source(snapshot, "Salesforce account record"),
        ]

    def _answer_activity(self, snapshot: _Snapshot) -> list[str]:
        last = _iso_date(snapshot.account, "last_activity_date")
        days = _days_since(last)
        if not last:
            headline = f"**{snapshot.name} has no recorded customer activity.**"
        elif days is None:
            headline = f"**Last recorded activity on {snapshot.name} was {last}.**"
        else:
            headline = (
                f"**Last recorded activity on {snapshot.name} was {last}, "
                f"{_plural(days, 'day')} ago.**"
            )
        lines = [
            headline,
            "",
            f"- Stage **{snapshot.stage or 'not recorded'}** for "
            f"{_plural(snapshot.days_in_stage, 'day')}.",
        ]
        if days is not None and days > 30:
            lines.append(
                "- That is past the 30-day threshold the deal-risk check treats as stale."
            )
        lines.append(self._source(snapshot, "Salesforce account record"))
        return lines

    def _answer_company_profile(self, snapshot: _Snapshot) -> list[str]:
        employees = int_value(snapshot.account, "employee_count")
        revenue = number_value(snapshot.account, "annual_revenue")
        return [
            f"**{snapshot.name} is a {snapshot.field('industry')} company with "
            f"{employees:,} employees and {format_money_compact(revenue)} in annual revenue.**",
            "",
            f"- Domain: **{snapshot.domain or 'not recorded'}**.",
            f"- Territory **{snapshot.field('territory')}**, "
            f"tier **{snapshot.field('target_tier')}**.",
            f"- Products on the account today: "
            f"**{self._joined(snapshot.products, 'none recorded')}**.",
            self._source(snapshot, "Salesforce account record"),
        ]

    def _answer_technology(self, snapshot: _Snapshot) -> list[str]:
        installed = string_values(snapshot.intel, "installed_technologies", "technologies")
        products = snapshot.products
        if not installed and not products:
            return [
                f"**No technology is recorded for {snapshot.name}.**",
                "",
                "- Neither the CRM record nor the ZoomInfo snapshot lists a vendor.",
                self._source(snapshot, "Salesforce account record"),
            ]
        counted = _plural(len(installed), "known technology", "known technologies")
        headline = f"**{snapshot.name} runs {counted}"
        headline += f": {self._joined(installed, '')}.**" if installed else ".**"
        lines = [
            headline,
            "",
            f"- Products recorded in the CRM: **{self._joined(products, 'none recorded')}**.",
        ]
        if snapshot.intel is None:
            lines.append(self._source(snapshot, "Salesforce account record"))
            return lines
        lines.append(
            f"- IT security headcount: **{int_value(snapshot.intel, 'it_security_headcount')}**."
        )
        lines.append(self._source(snapshot, f"{snapshot.intel_source} technographics"))
        return lines

    def _answer_intent(self, snapshot: _Snapshot) -> list[str]:
        if snapshot.intent is None:
            return [
                f"**No intent signal is recorded for {snapshot.name}.**",
                "",
                "- The local 6sense extract has no row for "
                f"**{snapshot.domain or 'this domain'}**.",
            ]
        score = int_value(snapshot.intent, "intent_score", "score")
        topics = string_values(snapshot.intent, "intent_topics")
        observed = _iso_date(snapshot.intent, "observed_at")
        return [
            f"**{snapshot.name} scores {score}/100 on intent**, in the "
            f"**{text_value(snapshot.intent, 'buying_stage', default='unrecorded')}** buying "
            f"stage with a **{text_value(snapshot.intent, 'profile_fit', default='unrecorded')}** "
            "profile fit.",
            "",
            f"- Active topics: **{self._joined(topics, 'none recorded')}**.",
            f"- Observed **{observed or 'date not recorded'}** via "
            f"**{text_value(snapshot.intent, 'source', default='intent feed')}**.",
        ]

    def _answer_contacts(self, snapshot: _Snapshot) -> list[str]:
        contacts = items_value(snapshot.intel, "key_contacts", "contacts")
        stakeholders = snapshot.stakeholder_count
        if not contacts:
            return [
                f"**No contacts are recorded for {snapshot.name}.**",
                "",
                f"- The CRM records **{_plural(stakeholders, 'engaged stakeholder')}** "
                "but the ZoomInfo snapshot has no named people.",
            ]
        rows = [
            "| {} | {} | {} | {} |".format(
                text_value(contact, "name", "full_name", default="Unknown"),
                text_value(contact, "title", default="Title not recorded"),
                text_value(contact, "seniority", default="—"),
                text_value(contact, "email", default="—"),
            )
            for contact in contacts
        ]
        return [
            f"**{snapshot.name} has {_plural(len(rows), 'known contact')}.**",
            "",
            "| Name | Title | Seniority | Email |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
            f"- The CRM records **{_plural(stakeholders, 'engaged stakeholder')}** on the deal.",
            self._source(snapshot, f"{snapshot.intel_source} contact records"),
        ]

    def _answer_risk(self, snapshot: _Snapshot) -> list[str]:
        if snapshot.risk is None:
            return [
                f"**No deal-risk assessment is available for {snapshot.name}.**",
                "",
                "- Ask for a *deal risk review* to run one now.",
            ]
        level = text_value(snapshot.risk, "risk_level", default="not recorded").title()
        score = int_value(snapshot.risk, "risk_score")
        flags = items_value(snapshot.risk, "flags")
        lines = [
            f"**Deal risk on {snapshot.name} is {level} ({score}/100).** "
            f"{text_value(snapshot.risk, 'summary')}",
            "",
        ]
        if flags:
            lines += [
                f"- **{text_value(flag, 'code', default='flag').replace('_', ' ').title()}** "
                f"({text_value(flag, 'severity', default='unspecified')}): "
                f"{text_value(flag, 'evidence')} {text_value(flag, 'recommendation')}"
                for flag in flags
            ]
        else:
            lines.append("- No hygiene flags fired on this account.")
        lines.append("")
        lines.append("_Ask for a “deal risk review” if you want the full workup._")
        return lines

    def _answer_tasks(self, snapshot: _Snapshot) -> list[str]:
        if snapshot.account is None:
            return self._answer_task_board(snapshot)
        tasks = snapshot.tasks
        if tasks is None or not tasks.total:
            return [
                f"**You have no tasks saved for {snapshot.name}.**",
                "",
                "- Add one with the **＋** button in **Accounts & tasks**.",
                f"- Or tell me: *“create a task for {snapshot.name} to send the "
                "security review pack”*.",
            ]
        if not tasks.open_items:
            headline = (
                f"**Every task for {snapshot.name} is done"
                f" — {_plural(tasks.total, 'task')} complete.**"
            )
        elif tasks.done_items:
            verb = "is" if len(tasks.open_items) == 1 else "are"
            headline = (
                f"**{len(tasks.open_items)} of {_plural(tasks.total, 'task')} {verb} "
                f"still open for {snapshot.name}.**"
            )
        else:
            headline = f"**{_plural(len(tasks.open_items), 'open task')} for {snapshot.name}.**"
        lines = [headline, ""]
        if tasks.open_items:
            lines += ["**Still open**", ""]
            lines += [f"- {item}" for item in tasks.open_items]
        if tasks.done_items:
            if tasks.open_items:
                lines.append("")
            lines += ["**Completed**", ""]
            lines += [f"- ~~{item}~~" for item in tasks.done_items]
        return lines

    def _answer_task_board(self, snapshot: _Snapshot) -> list[str]:
        """Summarise tasks across every account when none is selected."""
        with_tasks = [entry for entry in snapshot.board if entry.total]
        if not with_tasks:
            return [
                "**You have no tasks saved yet.**",
                "",
                "- Select an account in **Accounts & tasks** and add one with **＋**.",
                "- Or tell me: *“create a task for Apex Financial to send the "
                "security review pack”*.",
            ]
        total_open = sum(len(entry.open_items) for entry in with_tasks)
        return [
            f"**{_plural(total_open, 'task')} still open across "
            f"{_plural(len(with_tasks), 'account')}.**",
            "",
            *(
                f"- **{entry.account_name}** — {len(entry.open_items)} open, "
                f"{len(entry.done_items)} done"
                for entry in with_tasks
            ),
            "",
            "_Select an account to see its list, or ask about one by name._",
        ]

    def _answer_overview(self, snapshot: _Snapshot) -> list[str]:
        employees = int_value(snapshot.account, "employee_count")
        revenue = format_money_compact(number_value(snapshot.account, "annual_revenue"))
        open_amount = format_money(number_value(snapshot.account, "open_opportunity_amount"))
        lines = [
            f"**{snapshot.name}** — {snapshot.field('industry')}, {employees:,} employees, "
            f"{revenue} revenue, owned by {snapshot.field('owner_id', 'account_owner')} in "
            f"{snapshot.field('territory')}.",
            "",
            f"- **Deal:** stage {snapshot.stage or 'not recorded'}, {open_amount} open, "
            f"{_plural(snapshot.days_in_stage, 'day')} in stage.",
        ]
        if snapshot.intent is not None:
            topics = self._joined(
                string_values(snapshot.intent, "intent_topics"), "none recorded"
            )
            lines.append(
                f"- **Intent:** {int_value(snapshot.intent, 'intent_score', 'score')}/100, "
                f"{text_value(snapshot.intent, 'buying_stage', default='stage not recorded')}, "
                f"topics {topics}."
            )
        contacts = items_value(snapshot.intel, "key_contacts", "contacts")
        if contacts:
            lead = contacts[0]
            lines.append(
                f"- **People:** {_plural(len(contacts), 'known contact')}, starting with "
                f"{text_value(lead, 'name', 'full_name')} "
                f"({text_value(lead, 'title')})."
            )
        if snapshot.risk is not None:
            level = text_value(snapshot.risk, "risk_level", default="not recorded").title()
            lines.append(
                f"- **Risk:** {level} ({int_value(snapshot.risk, 'risk_score')}/100) — "
                f"{text_value(snapshot.risk, 'summary')}"
            )
        if snapshot.tasks is not None and snapshot.tasks.open_items:
            lines.append(
                f"- **Your tasks:** {_plural(len(snapshot.tasks.open_items), 'open task')}, "
                f"next up “{snapshot.tasks.open_items[0]}”."
            )
        lines += ["", "_Ask for an “account 360 healthcheck” if you want the full workup._"]
        return lines

    # -- Shared helpers -----------------------------------------------------

    @staticmethod
    def _joined(items: Sequence[str], empty: str) -> str:
        """Join ``items`` with commas, returning ``empty`` when there is nothing."""
        return ", ".join(items) if items else empty

    @staticmethod
    def _source(snapshot: _Snapshot, label: str) -> str:
        """Render the provenance footer shown under a factual answer."""
        target = snapshot.domain or snapshot.name
        return f"\n_Read from the {label} for {target}._"

    @staticmethod
    def _data_sources(topic: AccountQuestionTopic, snapshot: _Snapshot) -> tuple[str, ...]:
        """List the record types that contributed to an answer."""
        overview = AccountQuestionTopic.OVERVIEW
        reads: tuple[tuple[frozenset[AccountQuestionTopic], Any, str], ...] = (
            (frozenset(AccountQuestionTopic), snapshot.account, "Salesforce accounts"),
            (frozenset({AccountQuestionTopic.INTENT, overview}), snapshot.intent, "Intent signals"),
            (
                frozenset(
                    {AccountQuestionTopic.TECHNOLOGY, AccountQuestionTopic.CONTACTS, overview}
                ),
                snapshot.intel,
                "Technographics",
            ),
            (
                frozenset({AccountQuestionTopic.RISK, overview}),
                snapshot.risk,
                "Deal-risk assessment",
            ),
            (
                frozenset({AccountQuestionTopic.TASKS, overview}),
                snapshot.board or None,
                "Your saved tasks",
            ),
        )
        return tuple(
            dict.fromkeys(
                label for topics, record, label in reads if topic in topics and record is not None
            )
        )
