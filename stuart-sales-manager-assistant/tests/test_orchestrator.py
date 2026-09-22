"""Sales Manager routing, registry, and workflow wiring."""

from __future__ import annotations

import json
from pathlib import Path

from agents.orchestrator.agent import planner_agent, root_agent
from agents.orchestrator.prompt import (
    TASK_AGENT_IDS,
    build_orchestrator_instruction,
    build_planner_instruction,
    format_registry,
    load_registry,
)
from agents.orchestrator.workflow import StuartWorkflow
from models.routing_decision import RoutingDecision

SPECIALISTS = (
    "crm_intelligence_specialist",
    "activity_engagement_specialist",
    "rep_performance_specialist",
    "forecast_modeling_specialist",
    "knowledge_base_rag",
)


def test_exact_sales_manager_specialist_allowlist() -> None:
    assert tuple(TASK_AGENT_IDS) == SPECIALISTS
    assert set(root_agent.specialist_agents) == set(SPECIALISTS)


def test_registry_lists_only_sales_manager_specialists() -> None:
    catalog = load_registry()
    ids = [entry["id"] for entry in catalog["agents"]]
    assert ids == [*SPECIALISTS]
    assert all(entry["description"] and entry["capabilities"] for entry in catalog["agents"])
    task_only = format_registry(task_agents_only=True)
    assert all(agent_id in task_only for agent_id in SPECIALISTS)


def test_root_agent_keeps_enforced_workflow_contract() -> None:
    assert isinstance(root_agent, StuartWorkflow)
    assert root_agent.name == "central_orchestrator"
    assert [agent.name for agent in root_agent.sub_agents] == [
        "route_planner",
        *SPECIALISTS,
        "synthesis",
    ]
    assert planner_agent.output_schema.__name__ == "RoutingDecision"
    assert root_agent.final_writer_agent.name == "synthesis"


def test_prompts_are_manager_facing_and_tool_grounded() -> None:
    orchestrator = build_orchestrator_instruction()
    planner = build_planner_instruction()
    assert all(agent_id in orchestrator for agent_id in SPECIALISTS)
    assert "manager" in (orchestrator + planner).lower()
    assert "RoutingDecision" in planner
    assert all(
        heading in planner
        for heading in ("ROLE", "PERSONA", "OBJECTIVE", "INSTRUCTIONS", "GUARDRAILS")
    )


def test_planner_owns_conversation_and_never_states_facts() -> None:
    planner = build_planner_instruction().lower()
    assert "direct_reply" in planner
    assert "typos" in planner
    assert "clarifying question" in planner
    assert "never assert a business fact" in planner
    assert "off topic" in planner


def test_eval_prompts_name_only_real_specialists() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "routing.evalset.json"
    for case in json.loads(path.read_text(encoding="utf-8"))["eval_cases"]:
        turn = case["conversation"][0]
        expected = [
            call["name"]
            for call in turn["intermediate_data"]["tool_uses"]
            if call["name"] != "synthesis"
        ]
        assert all(name in SPECIALISTS for name in expected), case["eval_id"]


def test_routing_model_rejects_old_and_unknown_ids() -> None:
    decision = RoutingDecision.from_state(
        {
            "agents": [
                {"agent_id": "forecast_modeling_specialist"},
                {"agent_id": "synthesis"},
                {"agent_id": "unknown"},
            ]
        }
    )
    assert [route.agent_id for route in decision.agents] == ["forecast_modeling_specialist"]
