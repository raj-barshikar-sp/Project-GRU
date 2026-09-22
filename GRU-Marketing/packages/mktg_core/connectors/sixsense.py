"""6sense: account intent signals and segment building."""

from __future__ import annotations

from typing import Protocol

from ..contracts import Account, IntentSignal, SegmentFilter, SegmentResult
from ._fixtures import load


class SixSenseConnector(Protocol):
    def list_intent_signals(
        self, account_ids: list[str] | None = None
    ) -> list[IntentSignal]: ...
    def build_segment(
        self, name: str, filters: SegmentFilter, accounts: list[Account]
    ) -> SegmentResult: ...


class MockSixSense:
    def list_intent_signals(
        self, account_ids: list[str] | None = None
    ) -> list[IntentSignal]:
        signals = [IntentSignal(**row) for row in load("intent_signals.json")]
        if account_ids is not None:
            wanted = set(account_ids)
            signals = [s for s in signals if s.account_id in wanted]
        return signals

    def build_segment(
        self, name: str, filters: SegmentFilter, accounts: list[Account]
    ) -> SegmentResult:
        """Applies the filter set. Entirely deterministic.

        The reasoning happened upstream, when a Skill Agent turned a sentence
        like "fintech accounts surging on Zero Trust in EMEA" into this filter
        object. This method just executes it.
        """
        signals_by_account: dict[str, list[IntentSignal]] = {}
        for signal in self.list_intent_signals():
            signals_by_account.setdefault(signal.account_id, []).append(signal)

        matched: list[Account] = []
        for account in accounts:
            if filters.industries and account.industry not in filters.industries:
                continue
            if filters.regions and account.region not in filters.regions:
                continue
            if filters.countries and account.country not in filters.countries:
                continue
            if account.employee_count < filters.min_employee_count:
                continue
            if filters.target_accounts_only and not account.is_target_account:
                continue
            if filters.intent_keywords or filters.min_intent_score:
                signals = signals_by_account.get(account.id, [])
                wanted = {k.lower() for k in filters.intent_keywords}
                hit = any(
                    (not wanted or signal.keyword.lower() in wanted)
                    and signal.intent_score >= filters.min_intent_score
                    for signal in signals
                )
                if not hit:
                    continue
            matched.append(account)

        return SegmentResult(
            segment_id=f"SEG-MOCK-{abs(hash(name)) % 100_000:05d}",
            name=name,
            account_count=len(matched),
            account_ids=[a.id for a in matched],
            filter_summary=_describe(filters),
        )


def _describe(f: SegmentFilter) -> str:
    """Plain-English echo of the filters, so the user can check the agent's work."""
    parts: list[str] = []
    if f.industries:
        parts.append("industry in " + ", ".join(f.industries))
    if f.regions:
        parts.append("region in " + ", ".join(r.value for r in f.regions))
    if f.countries:
        parts.append("country in " + ", ".join(f.countries))
    if f.intent_keywords:
        parts.append("intent keyword in " + ", ".join(f.intent_keywords))
    if f.min_intent_score:
        parts.append(f"intent score >= {f.min_intent_score}")
    if f.min_employee_count:
        parts.append(f"employees >= {f.min_employee_count:,}")
    if f.target_accounts_only:
        parts.append("target accounts only")
    return "; ".join(parts) if parts else "no filters (all accounts)"
