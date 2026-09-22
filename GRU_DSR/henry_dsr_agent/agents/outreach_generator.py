"""Concise, channel-specific outreach generation."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import BaseAgent, MockLLMProvider, parse_json_output, value


class OutreachMessage(BaseModel):
    """One compliant outbound message."""

    channel: Literal["email", "call", "linkedin"]
    subject: str | None = None
    body: str
    word_count: int = Field(ge=1, le=124)
    cta: str


class OutreachResult(BaseModel):
    """Complete three-channel outreach sequence."""

    messages: list[OutreachMessage]
    personalization_basis: list[str]


class _DraftSet(BaseModel):
    email_subject: str
    email: str
    call: str
    linkedin: str


class OutreachGeneratorAgent(BaseAgent[OutreachResult]):
    """Generate plain-language email, call, and LinkedIn outreach."""

    BUZZWORDS = {
        "best-in-class",
        "cutting-edge",
        "game-changing",
        "revolutionary",
        "synergy",
        "leverage",
        "transformative",
        "world-class",
        "seamless",
    }
    CTAS = {
        "email": "Would Tuesday at 10:00 AM work for a 20-minute conversation?",
        "call": "Can we schedule 20 minutes on Tuesday to compare notes?",
        "linkedin": "Open to a 20-minute conversation Tuesday?",
    }

    async def run(
        self,
        *,
        account: Any,
        contact: Any | None = None,
        signals: list[Any] | None = None,
        positioning: Any | None = None,
        **_: Any,
    ) -> OutreachResult:
        """Create a validated sequence, falling back locally on invalid LLM output."""
        basis = self._basis(account, signals or [], positioning)
        drafts: _DraftSet | None = None
        if not isinstance(self.llm, MockLLMProvider):
            prompt = (
                "Return JSON with email_subject, email, call, linkedin. Each body must "
                "be under 125 words, use plain language, and end with a specific CTA. "
                f"Account: {value(account, 'name', 'account_name', default='the account')}. "
                f"Contact: {value(contact, 'name', 'full_name', default='there')}. "
                f"Evidence: {'; '.join(basis)}"
            )
            try:
                drafts = parse_json_output(_DraftSet, await self.llm.generate(prompt))
            except (ValueError, TypeError):
                drafts = None
        if drafts is None:
            drafts = self._fallback(account, contact, basis)

        messages = [
            self._message("email", drafts.email, drafts.email_subject),
            self._message("call", drafts.call),
            self._message("linkedin", drafts.linkedin),
        ]
        return OutreachResult(messages=messages, personalization_basis=basis)

    def _message(
        self,
        channel: Literal["email", "call", "linkedin"],
        body: str,
        subject: str | None = None,
    ) -> OutreachMessage:
        cleaned = self._remove_buzzwords(body)
        cta = self.CTAS[channel]
        if cta.lower().rstrip("?") not in cleaned.lower().rstrip("?"):
            cleaned = f"{cleaned.rstrip()} {cta}"
        words = cleaned.split()
        if len(words) >= 125:
            cta_words = cta.split()
            words = words[: 124 - len(cta_words)] + cta_words
            cleaned = " ".join(words)
        return OutreachMessage(
            channel=channel,
            subject=subject if channel == "email" else None,
            body=cleaned,
            word_count=len(cleaned.split()),
            cta=cta,
        )

    def _remove_buzzwords(self, text: str) -> str:
        cleaned = text
        for phrase in self.BUZZWORDS:
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def _basis(account: Any, signals: list[Any], positioning: Any) -> list[str]:
        facts: list[str] = []
        industry = value(account, "industry")
        if industry:
            facts.append(f"Industry: {industry}")
        for signal in signals[:2]:
            topic = value(signal, "topic", "intent_topic", "name")
            if topic:
                facts.append(f"Interest in {topic}")
        positions = value(positioning, "positions", default=[]) or []
        for position in positions[:1]:
            competitor = value(position, "competitor", "name")
            if competitor:
                facts.append(f"Uses {competitor}")
        return facts or ["No unverified personalization used"]

    def _fallback(self, account: Any, contact: Any, basis: list[str]) -> _DraftSet:
        company = str(value(account, "name", "account_name", default="your team"))
        first_name = str(value(contact, "first_name", default=""))
        if not first_name:
            first_name = str(value(contact, "name", "full_name", default="there")).split()[0]
        evidence = basis[0].replace("Industry: ", "").replace("Interest in ", "")
        return _DraftSet(
            email_subject=f"Identity security at {company}",
            email=(
                f"Hi {first_name}, I noticed {evidence} is relevant at {company}. "
                "Teams in this position often need a clearer view of identity access "
                "and faster follow-up on risky permissions. We can share how peers "
                "measure the gap without replacing their current process."
            ),
            call=(
                f"Hi {first_name}, this is Henry. I am calling because {evidence} "
                f"appears relevant at {company}. I would like to understand how your "
                "team finds and resolves risky identity access today."
            ),
            linkedin=(
                f"Hi {first_name}, I saw that {evidence} is relevant at {company}. "
                "I work with security teams reviewing risky identity access and "
                "thought a short comparison could be useful."
            ),
        )
