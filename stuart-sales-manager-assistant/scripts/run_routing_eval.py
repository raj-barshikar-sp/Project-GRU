"""Run the routing eval set and score name-level orchestration plus synthesis."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.adk.cli.cli_eval import _collect_eval_results, _collect_inferences
from google.adk.evaluation.base_eval_service import (
    InferenceConfig,
    InferenceRequest,
    InferenceStatus,
)
from google.adk.evaluation.eval_config import (
    EvalConfig,
    get_eval_metrics_from_config,
)
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.in_memory_eval_sets_manager import InMemoryEvalSetsManager
from google.adk.evaluation.local_eval_service import LocalEvalService
from google.adk.evaluation.metric_evaluator_registry import (
    register_custom_metrics_from_config,
)

from agents.orchestrator.agent import root_agent
from evals.metrics import (
    expected_agent_names,
    intermediate_authors,
    routing_pass,
    synthesis_format_pass,
)

APP = "orchestrator"
EVAL_SET_PATH = ROOT / "evals" / "routing.evalset.json"
CONFIG_PATH = ROOT / "evals" / "test_config.json"


def _text(content) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join(p.text for p in content.parts if getattr(p, "text", None))


async def run_once(out_path: Path) -> dict:
    started = time.time()
    eval_set = EvalSet.model_validate_json(
        EVAL_SET_PATH.read_text(encoding="utf-8")
    )
    eval_config = EvalConfig.model_validate_json(
        CONFIG_PATH.read_text(encoding="utf-8")
    )
    register_custom_metrics_from_config(eval_config)
    metrics = get_eval_metrics_from_config(eval_config)

    manager = InMemoryEvalSetsManager()
    manager.create_eval_set(APP, eval_set.eval_set_id)
    for case in eval_set.eval_cases:
        manager.add_eval_case(APP, eval_set.eval_set_id, case)

    expected_by_id = {
        case.eval_id: expected_agent_names(case.conversation[0])
        for case in eval_set.eval_cases
    }
    prompt_by_id = {
        case.eval_id: _text(case.conversation[0].user_content)
        for case in eval_set.eval_cases
    }

    service = LocalEvalService(root_agent=root_agent, eval_sets_manager=manager)
    inferences = await _collect_inferences(
        [
            InferenceRequest(
                app_name=APP,
                eval_set_id=eval_set.eval_set_id,
                inference_config=InferenceConfig(parallelism=4),
            )
        ],
        service,
    )
    successful = [row for row in inferences if row.status == InferenceStatus.SUCCESS]
    eval_results = []
    if successful:
        eval_results = await _collect_eval_results(successful, service, metrics)
    eval_by_id = {row.eval_id: row for row in eval_results}

    cases = []
    for inf in inferences:
        expected = expected_by_id.get(inf.eval_case_id, [])
        authors: list[str] = []
        response = ""
        if inf.inferences:
            authors = intermediate_authors(inf.inferences[0])
            response = _text(inf.inferences[0].final_response)
        routed = routing_pass(authors, expected)
        formatted = synthesis_format_pass(response, "synthesis" in expected)
        adk = eval_by_id.get(inf.eval_case_id)
        cases.append(
            {
                "eval_id": inf.eval_case_id,
                "prompt": prompt_by_id.get(inf.eval_case_id, ""),
                "inference_status": inf.status.name,
                "error": inf.error_message,
                "expected": expected,
                "authors": authors,
                "routing_pass": routed,
                "synthesis_format_pass": formatted,
                "end_to_end_pass": routed and formatted,
                "adk_status": adk.final_eval_status.name if adk else None,
                "response_preview": response[:400],
            }
        )

    n = len(cases)
    synth_n = sum(1 for case in cases if "synthesis" in case["expected"])
    summary = {
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec": round(time.time() - started, 1),
        "cases": n,
        "inference_failures": sum(
            1 for case in cases if case["inference_status"] != "SUCCESS"
        ),
        "routing_pass": sum(1 for case in cases if case["routing_pass"]),
        "routing_rate": sum(1 for case in cases if case["routing_pass"]) / n if n else 0,
        "synthesis_format_pass": sum(
            1 for case in cases if "synthesis" in case["expected"] and case["synthesis_format_pass"]
        ),
        "synthesis_cases": synth_n,
        "end_to_end_pass": sum(1 for case in cases if case["end_to_end_pass"]),
        "end_to_end_rate": (
            sum(1 for case in cases if case["end_to_end_pass"]) / n if n else 0
        ),
    }
    out_path.write_text(
        json.dumps({"summary": summary, "cases": cases}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/tmp/stuart-eval/results.json")
    args = parser.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_once(Path(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
