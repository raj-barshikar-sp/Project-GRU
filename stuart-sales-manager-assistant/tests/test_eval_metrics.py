"""Regression tests for the custom name-level eval gates."""

from __future__ import annotations

from google.adk.evaluation.eval_case import (
    IntermediateData,
    Invocation,
    InvocationEvent,
    InvocationEvents,
)
from google.genai import types

from evals.metrics import (
    intermediate_authors,
    routing_pass,
    synthesis_format_pass,
)
from models.synthesis_output import (
    RecommendedAction,
    SynthesisOutput,
    render_synthesis_markdown,
)


def test_routing_score_ignores_nested_tools_and_order_of_specialists() -> None:
    assert routing_pass(
        [
            "route_planner",
            "crm_intelligence_specialist",
            "activity_engagement_specialist",
            "synthesis",
        ],
        ["activity_engagement_specialist", "crm_intelligence_specialist", "synthesis"],
    )
    assert not routing_pass(
        ["route_planner", "synthesis"],
        ["crm_intelligence_specialist", "activity_engagement_specialist", "synthesis"],
    )
    assert routing_pass(
        ["route_planner", "crm_intelligence_specialist", "synthesis", "synthesis"],
        ["crm_intelligence_specialist", "synthesis"],
    )
    assert not routing_pass(
        ["route_planner", "crm_intelligence_specialist", "synthesis", "synthesis", "synthesis"],
        ["crm_intelligence_specialist", "synthesis"],
    )
    assert routing_pass(
        ["knowledge_base_rag", "synthesis"],
        ["knowledge_base_rag", "synthesis"],
    )


def test_intermediate_authors_reads_child_agent_events() -> None:
    invocation = Invocation(
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text="hello")]
        ),
        intermediate_data=IntermediateData(
            intermediate_responses=[
                ("route_planner", [types.Part.from_text(text="{}")]),
                ("crm_intelligence_specialist", [types.Part.from_text(text="{}")]),
            ]
        ),
    )
    assert intermediate_authors(invocation) == [
        "route_planner",
        "crm_intelligence_specialist",
    ]


def test_intermediate_authors_reads_invocation_events() -> None:
    invocation = Invocation(
        user_content=types.Content(
            role="user", parts=[types.Part.from_text(text="hello")]
        ),
        intermediate_data=InvocationEvents(
            invocation_events=[
                InvocationEvent(author="user", content=None),
                InvocationEvent(author="route_planner", content=None),
                InvocationEvent(author="crm_intelligence_specialist", content=None),
                InvocationEvent(author="synthesis", content=None),
            ]
        ),
    )
    assert intermediate_authors(invocation) == [
        "route_planner",
        "crm_intelligence_specialist",
        "synthesis",
    ]


def test_synthesis_format_gate_requires_the_briefing_sections() -> None:
    briefing = render_synthesis_markdown(
        SynthesisOutput(
            summary="You have 19 open deals. Global Logistics is the largest.",
            insights=["Global Logistics Corp is $580,000 and closes 2026-09-29."],
            actions=[RecommendedAction(action="Confirm board approval.")],
        )
    )
    assert synthesis_format_pass(briefing, expect_synthesis=True)
    assert not synthesis_format_pass(
        "You have 19 open deals.",
        expect_synthesis=True,
    )
    assert not synthesis_format_pass(
        briefing.replace(
            "You have 19 open deals. Global Logistics is the largest.",
            "Awaiting specialist findings.",
        ),
        expect_synthesis=True,
    )
    assert synthesis_format_pass("Hello!", expect_synthesis=False)
