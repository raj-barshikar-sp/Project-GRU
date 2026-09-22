"""Routing eval set parses as an ADK EvalSet without calling the live model."""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_set import EvalSet

EVALS_DIR = Path(__file__).resolve().parents[1] / "evals"
EVAL_SET_PATH = EVALS_DIR / "routing.evalset.json"
EVAL_CONFIG_PATH = EVALS_DIR / "test_config.json"

EXPECTED_TOOLS = {
    "greeting_no_tools": [],
    "crm_intelligence": ["crm_intelligence_specialist", "synthesis"],
    "activity_engagement": ["activity_engagement_specialist", "synthesis"],
    "rep_performance": ["rep_performance_specialist", "synthesis"],
    "forecast_modeling": ["forecast_modeling_specialist", "synthesis"],
    "knowledge_base": ["knowledge_base_rag", "synthesis"],
    "multi_specialist": [
        "crm_intelligence_specialist",
        "activity_engagement_specialist",
        "synthesis",
    ],
}


def test_routing_evalset_parses() -> None:
    payload = json.loads(EVAL_SET_PATH.read_text())
    eval_set = EvalSet.model_validate(payload)
    assert eval_set.eval_set_id == "stuart_routing"
    case_ids = [case.eval_id for case in eval_set.eval_cases]
    assert case_ids == list(EXPECTED_TOOLS)


def test_routing_evalset_expected_tools() -> None:
    eval_set = EvalSet.model_validate_json(
        EVAL_SET_PATH.read_text(encoding="utf-8")
    )
    for case in eval_set.eval_cases:
        assert case.conversation, case.eval_id
        invocation = case.conversation[0]
        uses = (
            invocation.intermediate_data.tool_uses
            if invocation.intermediate_data
            else []
        )
        names = [call.name for call in uses]
        assert names == EXPECTED_TOOLS[case.eval_id]
    specialists = {
        name
        for names in EXPECTED_TOOLS.values()
        for name in names
        if name != "synthesis"
    }
    assert specialists == {
        "crm_intelligence_specialist",
        "activity_engagement_specialist",
        "rep_performance_specialist",
        "forecast_modeling_specialist",
        "knowledge_base_rag",
    }


def test_eval_config_parses() -> None:
    config = EvalConfig.model_validate_json(
        EVAL_CONFIG_PATH.read_text(encoding="utf-8")
    )
    assert set(config.criteria) == {
        "orchestrator_routing_score",
        "synthesis_format_score",
    }
    assert config.custom_metrics is not None
    assert set(config.custom_metrics) == set(config.criteria)
    assert (
        config.custom_metrics[
            "orchestrator_routing_score"
        ].code_config.name
        == "evals.metrics.orchestrator_routing_score"
    )
