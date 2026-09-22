"""Structural checks on the agent tree.

These need no API key, so they run in CI on every commit. They exist to catch
the failures that are silent rather than loud: a template variable that never
gets substituted, a description too vague to route on, a write tool that has
crept into a read-only orchestrator.

Routing quality itself needs a model and lives in scripts/run_routing_evals.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from google.adk.tools.agent_tool import AgentTool

from root import marketing_orchestrator
from root.app import build_app

ROOT = Path(__file__).resolve().parents[1]

VALID_STATE_PREFIXES = (
    "analysis_", "events_", "mops_", "campaign_", "abm_", "content_", "brand_",
)
# Anything that changes a record in a source system.
WRITE_TOOL_NAMES = {
    "create_sfdc_campaign", "build_6sense_segment", "deploy_segment_to_marketo",
    "read_lead_file", "clean_lead_rows", "validate_lead_rows", "load_cleaned_list",
}


def walk(agent, seen=None):
    seen = seen or set()
    if id(agent) in seen:
        return
    seen.add(id(agent))
    yield agent
    for child in getattr(agent, "sub_agents", None) or []:
        yield from walk(child, seen)
    for tool in getattr(agent, "tools", None) or []:
        if isinstance(tool, AgentTool):
            yield from walk(tool.agent, seen)


ALL_AGENTS = list(walk(marketing_orchestrator))


def tool_names(agent) -> set[str]:
    names = set()
    for tool in getattr(agent, "tools", None) or []:
        names.add(getattr(tool, "__name__", None) or getattr(tool, "name", ""))
    return names


def by_name(name: str):
    return next(a for a in ALL_AGENTS if a.name == name)


# Steps inside a fixed chain are reached by position, never chosen by a router,
# so the rules about routing-grade descriptions do not apply to them.
CHAIN_STEPS = {
    "analysis_pipeline_deck_analyst", "analysis_pipeline_deck_writer",
    "analysis_demand_council_analyst", "analysis_demand_council_writer",
    "campaign_brief_deck_analyst", "campaign_brief_deck_writer",
    "events_brief_preparer", "events_brief_writers", "events_brief_merger",
    "events_brief_writer_1", "events_brief_writer_2", "events_brief_writer_3",
    "mops_list_load_reader", "mops_list_load_cleaner",
    "mops_list_load_validator", "mops_list_load_loader",
    "marketing_orchestrator",
}
ROUTABLE = [a for a in ALL_AGENTS if a.name not in CHAIN_STEPS]


# --- naming ---------------------------------------------------------------

def test_the_whole_tree_was_built():
    assert len(ALL_AGENTS) > 25, "expected the full seven-orchestrator tree"


def test_app_wraps_the_root_with_context_cache():
    app = build_app()
    assert app.root_agent is marketing_orchestrator
    assert app.context_cache_config is not None


def test_the_reply_contract_reaches_every_specialist():
    # The agent that answers is whichever one the router transferred to, so the
    # contract has to be applied app-wide rather than on the root agent alone.
    from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin

    from root.agent import REPLY_CONTRACT

    plugins = [p for p in build_app().plugins if isinstance(p, GlobalInstructionPlugin)]
    assert len(plugins) == 1
    assert plugins[0].global_instruction == REPLY_CONTRACT
    # ADK runs str instructions through session-state interpolation, which
    # treats braces as template slots and would fail on a stray one.
    assert "{" not in REPLY_CONTRACT and "}" not in REPLY_CONTRACT


def test_the_reply_contract_names_its_headings():
    from root.agent import REPLY_CONTRACT

    headings = [
        "## Summary",
        "## Key Insights",
        "## Recommended Actions",
        "## Artifacts",
        "## Receipt",
        "## Question",
        "## Cannot",
    ]
    assert all(heading in REPLY_CONTRACT for heading in headings)
    assert "Would create" in REPLY_CONTRACT
    assert 'Never "successfully created"' in REPLY_CONTRACT


def test_the_reply_contract_lets_a_specialist_omit_a_section():
    """Forcing every heading made agents write "another specialist does that".

    The performance analyst is told not to recommend changes, so a contract
    demanding a Recommended Actions section leaves it nothing honest to write.
    """
    from root.agent import REPLY_CONTRACT

    assert "All four headings must be present" not in REPLY_CONTRACT
    assert "Leave a heading out entirely" in REPLY_CONTRACT
    assert "Do not attach owner or timing" in REPLY_CONTRACT
    # Naming an internal specialist in the answer reads to the user as a refusal.
    assert "Never mention specialists" in REPLY_CONTRACT


def test_the_root_passes_through_an_already_structured_team_answer():
    from root.agent import INSTRUCTION

    assert "return that result" in INSTRUCTION
    assert "verbatim" in INSTRUCTION
    assert "Do not introduce it, summarise it, rewrite it" in INSTRUCTION
    assert "Only assemble a new answer when several team results" in INSTRUCTION


def test_the_coordinators_ask_the_model_for_its_thoughts():
    """The chat UI's Thinking panel is fed by `thought` parts on the stream.

    Gemini withholds those unless they are requested, so a coordinator with no
    planner leaves the panel with a header and nothing under it.
    """
    from google.adk.planners import BuiltInPlanner

    coordinators = [marketing_orchestrator] + [
        tool.agent for tool in marketing_orchestrator.tools
        if isinstance(tool, AgentTool)
    ]
    for agent in coordinators:
        assert isinstance(agent.planner, BuiltInPlanner), (
            f"{agent.name} streams no thoughts for the Thinking panel"
        )
        assert agent.planner.thinking_config.include_thoughts is True


def test_agent_names_are_unique():
    names = [a.name for a in ALL_AGENTS]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate agent names break routing: {duplicates}"


def test_all_seven_orchestrators_are_wired_in():
    expected = {
        "analysis_orchestrator", "events_orchestrator", "mops_orchestrator",
        "campaign_design_orchestrator", "abm_orchestrator",
        "content_orchestrator", "brand_orchestrator",
    }
    actual = {
        tool.agent.name for tool in marketing_orchestrator.tools
        if isinstance(tool, AgentTool)
    }
    assert actual == expected


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_agent_names_carry_a_domain_prefix(agent):
    """Names share one namespace across all seven teams, so they need prefixes."""
    allowed = ("analysis_", "events_", "mops_", "campaign_", "abm_",
               "content_", "brand_", "marketing_orchestrator")
    assert agent.name.startswith(allowed), (
        f"{agent.name} has no domain prefix and could collide with the other "
        f"half of the system"
    )


# --- descriptions, which are the routing logic ----------------------------

@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_every_agent_has_some_description(agent):
    assert agent.description, (
        f"{agent.name} has no description at all, which makes the tree "
        f"unreadable even where routing does not depend on it"
    )


@pytest.mark.parametrize("agent", ROUTABLE, ids=lambda a: a.name)
def test_routable_agents_have_a_routing_grade_description(agent):
    """Only agents a router chooses between need a description this rich."""
    assert len(agent.description) > 40, (
        f"{agent.name} is routed to but has a description too short to route "
        f"on: {agent.description!r}"
    )


def test_routable_specialists_say_what_they_are_not_for():
    """The 'NOT for' clause is what separates near neighbours."""
    missing = [a.name for a in ROUTABLE if "NOT" not in a.description]
    assert not missing, (
        f"these agents are routed to but do not say what they are NOT for, "
        f"which is how near neighbours get confused: {missing}"
    )


# --- session state --------------------------------------------------------

@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_output_keys_are_namespaced(agent):
    key = getattr(agent, "output_key", None)
    if key:
        assert key.startswith(VALID_STATE_PREFIXES), (
            f"{agent.name} writes to un-namespaced state key {key!r}, which "
            f"could collide with another team's"
        )


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_output_keys_are_valid_identifiers(agent):
    """ADK only substitutes template variables whose key is an identifier.

    A dotted key like `analysis.pipeline_health` fails silently: the template
    is left in the prompt as literal text and the agent reads the key name
    instead of the data. Nothing raises, which is what makes it dangerous.
    """
    key = getattr(agent, "output_key", None)
    if key:
        assert key.isidentifier(), (
            f"{agent.name} uses output_key {key!r}, which is not a valid "
            f"Python identifier, so nothing can read it via a template"
        )


@pytest.mark.parametrize("agent", ALL_AGENTS, ids=lambda a: a.name)
def test_template_variables_would_actually_substitute(agent):
    """Catch the same trap from the reading side."""
    instruction = getattr(agent, "instruction", "") or ""
    if not isinstance(instruction, str):
        return
    for raw in re.findall(r"\{([^{}]+)\}", instruction):
        name = raw.rstrip("?")
        assert name.isidentifier(), (
            f"{agent.name} references template variable {{{raw}}}, which is "
            f"not a valid identifier. ADK will leave it in the prompt as "
            f"literal text instead of substituting the value."
        )


def test_deck_writers_read_the_analysis_from_state():
    """The whole reason the deck chains are two steps."""
    for name in ("analysis_pipeline_deck_writer", "analysis_demand_council_writer"):
        assert "{analysis_pipeline_health?}" in by_name(name).instruction
    assert "{campaign_brief?}" in by_name("campaign_brief_deck_writer").instruction
    writer = by_name("campaign_brief_deck_writer").instruction.lower()
    assert "never refuse" in writer
    assert "cannot invent" not in writer
    analyst = by_name("campaign_brief_deck_analyst").instruction
    assert "get_named_campaign" in analyst
    assert "Do not refuse" in analyst


def test_the_analysts_feeding_the_deck_writers_write_that_key():
    for name in ("analysis_pipeline_deck_analyst", "analysis_demand_council_analyst"):
        assert by_name(name).output_key == "analysis_pipeline_health"
    assert by_name("campaign_brief_deck_analyst").output_key == "campaign_brief"


def test_brief_writers_and_merger_agree_on_their_state_keys():
    for n in (1, 2, 3):
        writer = by_name(f"events_brief_writer_{n}")
        assert f"{{events_brief_data_{n}?}}" in writer.instruction
        assert writer.output_key == f"events_brief_out_{n}"
        assert f"{{events_brief_out_{n}?}}" in by_name("events_brief_merger").instruction


# --- least privilege ------------------------------------------------------

def test_campaign_performance_can_read_pipeline_coverage():
    """Gap-to-target questions must not die as 'not in campaign records'."""
    names = tool_names(by_name("analysis_campaign_performance"))
    assert "get_pipeline_coverage" in names
    assert "get_campaign_performance" in names
    assert "get_pipeline_coverage" in by_name(
        "analysis_campaign_performance"
    ).instruction
    """A read-only orchestrator should be unable to change anything, by design."""
    for agent in walk(by_name("analysis_orchestrator")):
        assert not (tool_names(agent) & WRITE_TOOL_NAMES), (
            f"{agent.name} is inside the read-only Analysis tree but holds a "
            f"write tool"
        )


def test_events_orchestrator_holds_no_write_tools():
    for agent in walk(by_name("events_orchestrator")):
        assert not (tool_names(agent) & WRITE_TOOL_NAMES), (
            f"{agent.name} is inside the read-only Events tree but holds a "
            f"write tool"
        )


def test_only_marketing_ops_can_write():
    writers = {a.name for a in ALL_AGENTS if tool_names(a) & WRITE_TOOL_NAMES}
    mops = {a.name for a in walk(by_name("mops_orchestrator"))}
    assert writers <= mops, f"write tools found outside Marketing Ops: {writers - mops}"
    assert writers, "expected Marketing Ops to hold the write tools"


def test_coordinators_only_hold_agent_tools():
    """Coordinators may invoke agents but must hold no business/data tools."""
    assert marketing_orchestrator.tools
    assert all(isinstance(tool, AgentTool) for tool in marketing_orchestrator.tools)
    abm = by_name("abm_orchestrator")
    assert abm.tools
    assert all(isinstance(tool, AgentTool) for tool in abm.tools)
    assert not (by_name("analysis_orchestrator").tools or [])
    assert not (by_name("events_orchestrator").tools or [])


# --- chain shapes ---------------------------------------------------------

def test_list_load_runs_its_steps_in_the_required_order():
    """Validation must never come after the upload."""
    steps = [a.name for a in by_name("mops_list_load").sub_agents]
    assert steps == [
        "mops_list_load_reader",
        "mops_list_load_cleaner",
        "mops_list_load_validator",
        "mops_list_load_loader",
    ]


def test_deck_chains_analyse_before_they_write():
    for chain, analyst, writer in (
        ("analysis_pipeline_deck", "analysis_pipeline_deck_analyst",
         "analysis_pipeline_deck_writer"),
        ("analysis_demand_council_deck", "analysis_demand_council_analyst",
         "analysis_demand_council_writer"),
        ("campaign_brief_deck", "campaign_brief_deck_analyst",
         "campaign_brief_deck_writer"),
    ):
        steps = [a.name for a in by_name(chain).sub_agents]
        assert steps.index(analyst) < steps.index(writer)


def test_briefs_prepare_then_fan_out_then_merge():
    steps = [a.name for a in by_name("events_account_briefs").sub_agents]
    assert steps == ["events_brief_preparer", "events_brief_writers",
                     "events_brief_merger"]
    assert len(by_name("events_brief_writers").sub_agents) == 3


def test_abm_specialists_share_the_expected_state_chain():
    assert by_name("abm_account_intel").output_key == "abm_account_intel"
    assert "{abm_account_intel?}" in by_name("abm_gap_value").instruction
    assert "{abm_account_intel?}" in by_name("abm_messaging").instruction
    assert "{abm_gap_value?}" in by_name("abm_messaging").instruction
    package = by_name("abm_multichannel_package").instruction
    for key in ("abm_account_intel", "abm_gap_value", "abm_messaging"):
        assert f"{{{key}?}}" in package


def test_abm_orchestrator_requires_all_requested_steps_and_rejects_other_domains():
    instruction = by_name("abm_orchestrator").instruction
    assert "call every required specialist" in instruction
    assert "Do not stop after the first specialist responds" in instruction
    assert "outside your scope" in instruction


# --- the evalset ----------------------------------------------------------

def test_evalset_only_references_agents_that_exist():
    """A typo in the evalset would otherwise look like a routing failure."""
    evalset = json.loads((ROOT / "evals/routing.evalset.json").read_text())
    names = {a.name for a in ALL_AGENTS}
    for case in evalset["cases"]:
        if case.get("expect_orchestrator"):
            assert case["expect_orchestrator"] in names, (
                f"{case['id']} expects unknown orchestrator "
                f"{case['expect_orchestrator']!r}")
        if case.get("expect_agent"):
            assert case["expect_agent"] in names, (
                f"{case['id']} expects unknown agent {case['expect_agent']!r}")
        expected_paths = [case.get("expect_agents", [])]
        expected_paths.extend(case.get("expect_agents_by_turn", []))
        for path in expected_paths:
            unknown = set(path) - names
            assert not unknown, (
                f"{case['id']} expects unknown agents {sorted(unknown)}")


def test_evalset_covers_every_orchestrator():
    evalset = json.loads((ROOT / "evals/routing.evalset.json").read_text())
    covered = {
        c["expect_orchestrator"] for c in evalset["cases"]
        if c.get("expect_orchestrator")
    }
    expected = {
        tool.agent.name for tool in marketing_orchestrator.tools
        if isinstance(tool, AgentTool)
    }
    assert covered == expected


def test_evalset_is_big_enough_to_be_worth_running():
    evalset = json.loads((ROOT / "evals/routing.evalset.json").read_text())
    assert len(evalset["cases"]) >= 40
    ambiguous = [c for c in evalset["cases"] if c["id"].startswith("amb-")]
    assert len(ambiguous) >= 8, (
        "the ambiguous cases are the ones that actually catch routing bugs"
    )
