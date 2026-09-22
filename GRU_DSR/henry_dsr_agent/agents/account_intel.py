"""Account intelligence and decision-maker prioritization."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import BaseAgent, invoke_tool, value


class PrioritizedContact(BaseModel):
    """A contact ranked for an identity-security sales motion."""

    name: str
    title: str
    rank: int = Field(ge=1)
    rationale: str
    email: str | None = None
    linkedin_url: str | None = None


class AccountIntelResult(BaseModel):
    """Technographic summary and ordered buying committee."""

    account_name: str
    installed_technology: list[str]
    decision_makers: list[PrioritizedContact]
    summary: str


class AccountIntelAgent(BaseAgent[AccountIntelResult]):
    """Enrich an account and order likely decision makers by persona."""

    def __init__(self, zoominfo_tool: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.zoominfo_tool = zoominfo_tool

    async def run(
        self,
        *,
        account: Any,
        contacts: list[Any] | None = None,
        technographics: Any | None = None,
        **_: Any,
    ) -> AccountIntelResult:
        """Return deterministic account intelligence, enriching when needed."""
        account_name = str(
            value(account, "name", "account_name", "company", default="Unknown account")
        )
        enrichment = None
        if self.zoominfo_tool is not None and (contacts is None or technographics is None):
            enrichment = await invoke_tool(
                self.zoominfo_tool,
                (
                    "get_tech_stack_and_contacts",
                    "get_account_intel",
                    "enrich_account",
                    "lookup_account",
                    "search",
                ),
                domain=value(account, "domain", default=account),
            )
        contacts = contacts or value(
            enrichment, "contacts", "people", "key_contacts", default=[]
        ) or []
        technographics = technographics or value(
            enrichment, "technographics", "technologies", "installed_technology"
        )
        technologies = self._technologies(technographics)
        ordered = sorted(contacts, key=self._persona_order)
        decision_makers = [
            PrioritizedContact(
                name=str(value(contact, "name", "full_name", default="Unknown")),
                title=str(value(contact, "title", "job_title", default="Unknown title")),
                rank=index,
                rationale=self._rationale(contact),
                email=value(contact, "email", "email_address"),
                linkedin_url=value(contact, "linkedin_url", "linkedin", "profile_url"),
            )
            for index, contact in enumerate(ordered, start=1)
        ]
        lead = decision_makers[0].title if decision_makers else "no identified security leader"
        return AccountIntelResult(
            account_name=account_name,
            installed_technology=technologies,
            decision_makers=decision_makers,
            summary=(
                f"{account_name}: {len(technologies)} installed technologies and "
                f"{len(decision_makers)} relevant contacts; start with {lead}."
            ),
        )

    @staticmethod
    def _persona_order(contact: Any) -> tuple[int, str]:
        title = str(value(contact, "title", "job_title", default="")).lower()
        if "chief information security" in title or "ciso" in title:
            tier = 0
        elif ("vp" in title or "vice president" in title) and (
            "iam" in title or "identity" in title or "access management" in title
        ):
            tier = 1
        elif "director" in title and (
            "iam" in title or "identity" in title or "access management" in title
        ):
            tier = 2
        elif "security operations" in title or "secops" in title or "soc" in title:
            tier = 3
        else:
            tier = 4
        return tier, str(value(contact, "name", "full_name", default=""))

    @classmethod
    def _rationale(cls, contact: Any) -> str:
        tier = cls._persona_order(contact)[0]
        return {
            0: "Executive security owner; prioritize for strategic sponsorship.",
            1: "Senior IAM owner; likely budget and program authority.",
            2: "IAM program leader; likely evaluation and implementation authority.",
            3: "Security operations stakeholder; validate operational pain and impact.",
            4: "Adjacent stakeholder; engage after core security and IAM leaders.",
        }[tier]

    @staticmethod
    def _technologies(source: Any) -> list[str]:
        raw = value(
            source,
            "technologies",
            "installed_technology",
            "installed_technologies",
            "products",
            default=source or [],
        )
        if isinstance(raw, str):
            raw = [raw]
        return sorted(
            {
                str(value(item, "name", "product", "vendor", default=item)).strip()
                for item in raw
                if item
            }
        )
