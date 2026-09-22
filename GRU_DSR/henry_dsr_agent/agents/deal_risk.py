"""Deterministic deal-risk inspection."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import BaseAgent, value


class RiskFlag(BaseModel):
    """One actionable deal risk."""

    code: Literal["missing_bva", "stale_deal", "single_threaded"]
    severity: Literal["medium", "high"]
    evidence: str
    recommendation: str


class DealRiskResult(BaseModel):
    """Overall deal health and its underlying flags."""

    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(ge=0, le=100)
    flags: list[RiskFlag]
    summary: str


class DealRiskAgent(BaseAgent[DealRiskResult]):
    """Flag missing value analysis, stale activity, and contact concentration."""

    async def run(
        self,
        *,
        opportunity: Any,
        as_of: datetime | None = None,
        **_: Any,
    ) -> DealRiskResult:
        """Evaluate three transparent deal hygiene rules."""
        now = as_of or datetime.now(timezone.utc)
        flags: list[RiskFlag] = []
        bva = value(
            opportunity,
            "bva",
            "business_value_assessment",
            "business_value_analysis",
            "value_case",
        )
        bva_complete = value(opportunity, "bva_complete")
        if not bva and bva_complete is not True:
            flags.append(
                RiskFlag(
                    code="missing_bva",
                    severity="high",
                    evidence="No business value assessment is attached.",
                    recommendation="Document measurable outcomes, baseline, and economic impact.",
                )
            )

        days = self._days_since_activity(opportunity, now)
        if days > 30:
            flags.append(
                RiskFlag(
                    code="stale_deal",
                    severity="high",
                    evidence=f"No recorded customer activity for {days} days.",
                    recommendation="Reconfirm priority, timeline, and a dated next step.",
                )
            )

        contacts = (
            value(
                opportunity,
                "engaged_contacts",
                "contacts",
                "stakeholders",
                "contact_roles",
                default=[],
            )
            or []
        )
        unique_contacts = {
            str(value(contact, "id", "contact_id", "email", "name", default=contact))
            for contact in contacts
        }
        recorded_count = value(opportunity, "stakeholder_count")
        try:
            committee_size = (
                int(recorded_count) if recorded_count is not None else len(unique_contacts)
            )
        except (TypeError, ValueError):
            committee_size = len(unique_contacts)
        committee_size = max(committee_size, len(unique_contacts))
        if committee_size <= 1:
            flags.append(
                RiskFlag(
                    code="single_threaded",
                    severity="medium",
                    evidence=f"Only {committee_size} distinct stakeholder is engaged.",
                    recommendation=(
                        "Add an economic buyer and a technical or operational stakeholder."
                    ),
                )
            )

        score = min(100, sum(35 if flag.severity == "high" else 25 for flag in flags))
        level: Literal["low", "medium", "high"] = (
            "high" if score >= 60 else "medium" if score >= 25 else "low"
        )
        return DealRiskResult(
            risk_level=level,
            risk_score=score,
            flags=flags,
            summary=(
                "No material hygiene risks detected."
                if not flags
                else f"{len(flags)} risk(s) detected; overall risk is {level}."
            ),
        )

    @staticmethod
    def _days_since_activity(opportunity: Any, now: datetime) -> int:
        raw = value(
            opportunity,
            "last_activity_date",
            "last_activity_at",
            "last_activity",
            "last_contacted_at",
            "updated_at",
        )
        if raw is None:
            return 365
        if isinstance(raw, date) and not isinstance(raw, datetime):
            parsed = datetime.combine(raw, datetime.min.time(), tzinfo=timezone.utc)
        elif isinstance(raw, datetime):
            parsed = raw
        else:
            try:
                parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return 365
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (now - parsed.astimezone(timezone.utc)).days)
