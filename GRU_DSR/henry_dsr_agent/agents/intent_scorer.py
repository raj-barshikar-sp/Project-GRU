"""Explainable account intent scoring."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from .base import BaseAgent, value


class ScoreFactor(BaseModel):
    """One normalized component of an intent score."""

    name: str
    raw_value: str
    normalized_score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    contribution: float = Field(ge=0.0)
    explanation: str


class IntentScoreResult(BaseModel):
    """Rankable intent score with an audit trail."""

    score: float = Field(ge=0.0, le=100.0)
    priority: str
    factors: list[ScoreFactor]
    rationale: str


class IntentScorerAgent(BaseAgent[IntentScoreResult]):
    """Score accounts using intent, stage, profile fit, and CRM recency."""

    WEIGHTS: ClassVar[dict[str, float]] = {
        "intent": 0.40,
        "buying_stage": 0.25,
        "profile_fit": 0.20,
        "crm_recency": 0.15,
    }
    STAGES: ClassVar[dict[str, float]] = {
        "decision": 100.0,
        "purchase": 100.0,
        "evaluation": 85.0,
        "consideration": 70.0,
        "research": 50.0,
        "awareness": 30.0,
        "unknown": 20.0,
    }

    async def run(
        self,
        *,
        intent: Any,
        account: Any | None = None,
        as_of: datetime | None = None,
        **_: Any,
    ) -> IntentScoreResult:
        """Calculate a deterministic weighted score."""
        now = as_of or datetime.now(timezone.utc)
        raw_intent = float(value(intent, "intent_score", "score", "strength", default=0))
        intent_score = raw_intent * 100.0 if 0.0 <= raw_intent <= 1.0 else raw_intent
        intent_score = self._clamp(intent_score)

        stage = str(
            value(intent, "buying_stage", "stage", "journey_stage", default="unknown")
        ).lower()
        stage_score = next(
            (score for name, score in self.STAGES.items() if name in stage),
            self.STAGES["unknown"],
        )
        profile_score = self._profile_fit(account, intent)
        days = self._days_since_activity(account, now)
        recency_score = 100.0 if days <= 7 else 80.0 if days <= 30 else 45.0 if days <= 90 else 10.0

        specs = [
            ("intent", str(raw_intent), intent_score, "Observed third-party intent strength."),
            ("buying_stage", stage, stage_score, f"Buying stage mapped from '{stage}'."),
            (
                "profile_fit",
                f"{profile_score:.0f}",
                profile_score,
                "Fit against account/profile signals.",
            ),
            ("crm_recency", f"{days} days", recency_score, "Time since the latest CRM activity."),
        ]
        factors = [
            ScoreFactor(
                name=name,
                raw_value=raw,
                normalized_score=normalized,
                weight=self.WEIGHTS[name],
                contribution=round(normalized * self.WEIGHTS[name], 2),
                explanation=explanation,
            )
            for name, raw, normalized, explanation in specs
        ]
        score = round(sum(item.contribution for item in factors), 1)
        priority = "high" if score >= 75 else "medium" if score >= 50 else "low"
        strongest = max(factors, key=lambda item: item.contribution)
        return IntentScoreResult(
            score=score,
            priority=priority,
            factors=factors,
            rationale=(
                f"{priority.title()} priority ({score}/100); strongest factor is "
                f"{strongest.name.replace('_', ' ')}."
            ),
        )

    @staticmethod
    def _clamp(number: float) -> float:
        return max(0.0, min(100.0, number))

    def _profile_fit(self, account: Any, intent: Any) -> float:
        explicit = value(
            account,
            "profile_fit_score",
            "fit_score",
            "icp_score",
            default=value(intent, "profile_fit", "fit_score"),
        )
        if explicit is not None:
            fit_labels = {"strong": 100.0, "moderate": 65.0, "weak": 30.0}
            normalized = str(explicit).strip().lower()
            if normalized in fit_labels:
                return fit_labels[normalized]
            number = float(explicit)
            return self._clamp(number * 100.0 if 0.0 <= number <= 1.0 else number)
        points = 0.0
        if value(account, "industry"):
            points += 25.0
        if value(account, "employee_count", "employees", "company_size"):
            points += 25.0
        if value(account, "revenue", "annual_revenue"):
            points += 25.0
        if value(account, "region", "country", "territory"):
            points += 25.0
        return points

    @staticmethod
    def _days_since_activity(account: Any, now: datetime) -> int:
        raw = value(
            account,
            "last_activity_date",
            "last_activity_at",
            "last_contacted_at",
            "last_activity",
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
