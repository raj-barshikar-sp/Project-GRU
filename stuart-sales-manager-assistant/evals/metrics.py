"""Name-level routing and deterministic synthesis-quality metrics."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from google.adk.evaluation.eval_case import (
    IntermediateData,
    Invocation,
    InvocationEvents,
    get_all_tool_calls,
)
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.evaluator import (
    EvaluationResult,
    PerInvocationResult,
)

from agents.orchestrator.prompt import TASK_AGENT_IDS

_HEADINGS = (
    "## Summary",
    "## Key Insights",
    "## Recommended Actions",
    "## Artifacts",
)
_PLACEHOLDER_RE = re.compile(r"\[[A-Z][A-Z0-9_ /-]{1,40}\]")
_HOLLOW_RE = re.compile(
    r"awaiting (?:specialist|findings)|ha(?:ve|s) not (?:yet )?received|"
    r"underlying data .* not provided|ensure the orchestrator|"
    r"structured findings .* missing|"
    r"couldn't produce a reliable briefing|"
    r"findings need to be regenerated|"
    r"no specific numeric|"
    r"missing specific (?:performance )?data|"
    r"fresh (?:reporting )?pull|"
    r"not returned in the current records|"
    r"currently missing .* (?:coverage|kpi|metrics|performance)|"
    r"records to populate",
    re.IGNORECASE,
)


def _content_text(content: Any) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join(
        part.text for part in content.parts if getattr(part, "text", None)
    )


def intermediate_authors(invocation: Invocation) -> list[str]:
    """Return child-agent authors captured by ADK inference."""
    intermediate = invocation.intermediate_data
    if isinstance(intermediate, IntermediateData):
        return [
            author
            for author, _parts in intermediate.intermediate_responses
            if author
        ]
    if isinstance(intermediate, InvocationEvents):
        return [
            event.author
            for event in intermediate.invocation_events
            if event.author and event.author != "user"
        ]
    return []


def expected_agent_names(invocation: Invocation) -> list[str]:
    """Read specialist names from the eval-set's tool trajectory fixture."""
    return [
        call.name
        for call in get_all_tool_calls(invocation.intermediate_data)
        if call.name
    ]


def routing_pass(actual_authors: list[str], expected_names: list[str]) -> bool:
    """Score selected child agents without unstable function-call args."""
    actual_tasks = [
        name for name in actual_authors if name in TASK_AGENT_IDS
    ]
    expected_tasks = [
        name for name in expected_names if name in TASK_AGENT_IDS
    ]
    if set(actual_tasks) != set(expected_tasks):
        return False
    expected_synthesis = "synthesis" in expected_names
    synthesis_count = actual_authors.count("synthesis")
    if expected_synthesis:
        relevant = [
            name
            for name in actual_authors
            if name in TASK_AGENT_IDS or name == "synthesis"
        ]
        return (
            1 <= synthesis_count <= 2
            and bool(relevant)
            and relevant[-1] == "synthesis"
        )
    return synthesis_count == 0


def synthesis_format_pass(text: str, expect_synthesis: bool) -> bool:
    """Validate the final briefing contract, including no preamble."""
    stripped = text.strip()
    if not stripped:
        return False
    if not expect_synthesis:
        return not any(heading in stripped for heading in _HEADINGS)
    positions = [stripped.find(heading) for heading in _HEADINGS]
    if positions[0] != 0 or any(position < 0 for position in positions):
        return False
    if positions != sorted(positions):
        return False
    if _PLACEHOLDER_RE.search(stripped) or _HOLLOW_RE.search(stripped):
        return False
    lowered = stripped.lower()
    leaks = (
        *TASK_AGENT_IDS,
        "orchestrator",
        "synthesis",
        "single_turn",
        "route_planner",
    )
    return not any(term.lower() in lowered for term in leaks)


def _evaluation(
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    scorer: Callable[[Invocation, Invocation | None], bool],
) -> EvaluationResult:
    expected = expected_invocations or [None] * len(actual_invocations)
    rows: list[PerInvocationResult] = []
    for actual, gold in zip(actual_invocations, expected, strict=True):
        passed = scorer(actual, gold)
        rows.append(
            PerInvocationResult(
                actual_invocation=actual,
                expected_invocation=gold,
                score=1.0 if passed else 0.0,
                eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
            )
        )
    score = sum(row.score or 0 for row in rows) / len(rows) if rows else 0.0
    return EvaluationResult(
        overall_score=score,
        overall_eval_status=(
            EvalStatus.PASSED if score == 1.0 else EvalStatus.FAILED
        ),
        per_invocation_results=rows,
    )


def orchestrator_routing_score(
    _metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    _scenario: Any = None,
) -> EvaluationResult:
    """ADK custom metric for child-agent selection and synthesis ordering."""
    return _evaluation(
        actual_invocations,
        expected_invocations,
        lambda actual, gold: routing_pass(
            intermediate_authors(actual),
            expected_agent_names(gold) if gold else [],
        ),
    )


def synthesis_format_score(
    _metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None,
    _scenario: Any = None,
) -> EvaluationResult:
    """ADK custom metric for the final deterministic markdown contract."""
    return _evaluation(
        actual_invocations,
        expected_invocations,
        lambda actual, gold: synthesis_format_pass(
            _content_text(actual.final_response),
            bool(gold and "synthesis" in expected_agent_names(gold)),
        ),
    )
