"""Runs the routing evalset against the real root orchestrator.

This needs a model API key, so it is a script rather than a pytest test. The
structural checks that do not need a key live in tests/test_structure.py.

    export GOOGLE_API_KEY=...
    python scripts/run_routing_evals.py
    python scripts/run_routing_evals.py --case amb-01

It works by watching which agents the request is transferred to, rather than
judging the final answer. Routing is what we are testing, and asking a model to
grade another model's prose would make the test slower and less trustworthy
than simply looking at where the request went.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from root import build_runner  # noqa: E402

EVALSET = ROOT / "evals/routing.evalset.json"


async def route_turn(
    runner: InMemoryRunner, session_id: str, prompt: str
) -> tuple[list[str], str]:
    """Send one turn and record which agents it reached."""
    visited: list[str] = []
    final_text = ""

    async for event in runner.run_async(
        user_id="eval",
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.author and event.author not in visited:
            visited.append(event.author)
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text.strip():
                final_text = text.strip()

    return visited, final_text


def contains_in_order(visited: list[str], expected: list[str]) -> bool:
    """Whether expected is an ordered (not necessarily contiguous) subsequence."""
    remaining = iter(visited)
    return all(any(actual == wanted for actual in remaining) for wanted in expected)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="Run a single case id, e.g. amb-01")
    parser.add_argument("--verbose", action="store_true",
                        help="Print each answer as well as the routing")
    args = parser.parse_args()

    evalset = json.loads(EVALSET.read_text())
    cases = evalset["cases"]
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"No case with id {args.case!r}")
            return 2

    runner = build_runner("routing_eval")

    passed = failed = 0
    failures: list[str] = []

    for case in cases:
        session = await runner.session_service.create_session(
            app_name=runner.app_name, user_id="eval")
        prompts = case.get("turns") or [case["prompt"]]
        visits_by_turn = []
        answers = []
        for prompt in prompts:
            visited, answer = await route_turn(runner, session.id, prompt)
            visits_by_turn.append(visited)
            answers.append(answer)

        visited = [name for turn in visits_by_turn for name in turn]
        missing = []
        expected_path = case.get("expect_agents")
        expected_by_turn = case.get("expect_agents_by_turn")

        if expected_path and not contains_in_order(visited, expected_path):
            missing.append(f"ordered path {' -> '.join(expected_path)}")
        elif expected_by_turn:
            for turn_number, (actual, expected) in enumerate(
                zip(visits_by_turn, expected_by_turn, strict=True), start=1
            ):
                if not contains_in_order(actual, expected):
                    missing.append(
                        f"turn {turn_number} path {' -> '.join(expected)}")
        else:
            want_orch = case["expect_orchestrator"]
            want_agent = case.get("expect_agent")
            if want_orch not in visited:
                missing.append(f"orchestrator {want_orch}")
            if want_agent is not None and want_agent not in visited:
                missing.append(f"agent {want_agent}")

        if not missing:
            passed += 1
            mark = "PASS"
        else:
            failed += 1
            mark = "FAIL"
            failures.append(
                f"  {case['id']}: {prompts[0]}\n"
                f"      wanted {' and '.join(missing)}\n"
                f"      went to "
                + " | ".join(" -> ".join(turn) for turn in visits_by_turn)
            )

        print(f"[{mark}] {case['id']:<8} {prompts[0][:62]}", flush=True)
        if args.verbose and answers[-1]:
            print(f"         {answers[-1][:180]}")

    total = passed + failed
    print(f"\n{passed}/{total} routed correctly.")
    if failures:
        print("\nFailures:")
        print("\n".join(failures))
        print(
            "\nRouting is driven by each agent's `description`. Fix the "
            "description that is too vague or too greedy, then re-run."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
