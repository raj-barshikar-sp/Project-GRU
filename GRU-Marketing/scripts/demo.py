"""End-to-end demo of the marketing agents system.

Five requests through the real root orchestrator: one for each of the three
orchestrators we own, one that produces a PowerPoint file, and one that lands
in the other half of the system to show the routing boundary works.

Needs a model API key:

    export GOOGLE_API_KEY=...
    python scripts/demo.py
    python scripts/demo.py --only pipeline
    python scripts/demo.py --list

Every run prints the path the request took through the agent tree, because in
a seven-orchestrator system the routing is usually the interesting part.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from google.genai import types  # noqa: E402
from mktg_core.profile import current_user  # noqa: E402

from root import build_runner  # noqa: E402

ME = current_user()

SCENARIOS = {
    "pipeline": {
        "title": "Analysis - pipeline health",
        "prompt": "How is our pipeline looking? Are we going to hit our number?",
        "expect": (
            "Should route to analysis_pipeline_health and lead with EMEA "
            "sitting at 1.46x coverage against a 2.0x target."
        ),
    },
    "budget": {
        "title": "Analysis - where to move budget",
        "prompt": "Where should we move budget to get more pipeline next quarter?",
        "expect": (
            "Should route to analysis_improvement_recommender and argue for "
            "moving spend out of Paid Social, which costs about 21x more per "
            "opportunity than the Zero Trust webinar."
        ),
    },
    "deck": {
        "title": "Analysis - build the pipeline deck (writes a .pptx)",
        "prompt": "Build me the pipeline deck for this week's review.",
        "expect": (
            "Should run the two-step chain, analyse then write, and save a "
            "file under output/decks/."
        ),
    },
    "event": {
        "title": "Regional Events - where to run an event",
        "prompt": (
            "Analyse accounts with no opportunity and tell me where we should "
            "run our next field event, and what the session should be about."
        ),
        "expect": (
            "Should route to events_location_topic and recommend Munich or "
            "Frankfurt on a Zero Trust theme, over the smaller Singapore SASE "
            "cluster."
        ),
    },
    "room": {
        "title": "Regional Events - pipeline in the room",
        "prompt": "Summarise the pipeline in the room for the Munich roundtable.",
        "expect": (
            "Should route to events_pipeline_in_room, total the open pipeline "
            "across attending accounts, and separate the accounts with "
            "nothing open."
        ),
    },
    "segment": {
        "title": "Marketing Ops - build a 6sense segment",
        "prompt": (
            "Build me a segment in 6sense of financial services accounts in "
            "EMEA that are surging on Zero Trust."
        ),
        "expect": (
            "Should route to mops_orchestrator, translate 'surging' into a "
            "minimum intent score of 80, and echo the filters back."
        ),
    },
    "listload": {
        "title": "Marketing Ops - list load (four fixed steps)",
        "prompt": "Load event_leads_munich.csv into Marketo for me.",
        "expect": (
            "Should run all four steps in order and reject the planted bad "
            "rows: a blank email, a malformed address, a duplicate and an "
            "internal address."
        ),
    },
    "handoff": {
        "title": "Campaign Design - campaign brief",
        "prompt": "Build me a campaign brief for the Q4 Zero Trust launch.",
        "expect": (
            "Should route to campaign_design_orchestrator and produce a "
            "structured brief saved under output/campaign/."
        ),
    },
    "abm": {
        "title": "ABM - top accounts in EMEA",
        "prompt": "What are my top accounts in EMEA for ABM?",
        "expect": (
            "Should route to abm_account_selection and rank Munich/Frankfurt "
            "Zero Trust cluster accounts highly."
        ),
    },
    "brand": {
        "title": "Brand - share of voice",
        "prompt": "How is our share of voice vs CyberArk looking?",
        "expect": (
            "Should route to brand_share_of_voice and show SailPoint trailing "
            "CyberArk in category mentions."
        ),
    },
}


async def run_scenario(runner: InMemoryRunner, key: str, scenario: dict) -> None:
    print("\n" + "=" * 78)
    print(f"  {scenario['title']}")
    print("=" * 78)
    print(f"\nUser: {scenario['prompt']}\n")
    print(f"Expected: {scenario['expect']}\n")

    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=ME["email"],
        state={"current_user": ME},
    )

    started = time.monotonic()
    path: list[str] = []
    tools_called: list[str] = []
    answer = ""

    async for event in runner.run_async(
        user_id=ME["email"],
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text=scenario["prompt"])]),
    ):
        if event.author and (not path or path[-1] != event.author):
            path.append(event.author)
        for call in event.get_function_calls() or []:
            if call.name != "transfer_to_agent":
                tools_called.append(call.name)
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text.strip():
                answer = text.strip()

    elapsed = time.monotonic() - started

    print("-" * 78)
    print(answer or "(no final answer produced)")
    print("-" * 78)
    print(f"Route:  {' -> '.join(path)}")
    if tools_called:
        print(f"Tools:  {', '.join(dict.fromkeys(tools_called))}")
    print(f"Took:   {elapsed:.1f}s")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append",
                        help="Run only these scenarios, by key. Repeatable.")
    parser.add_argument("--list", action="store_true",
                        help="List the scenario keys and exit.")
    args = parser.parse_args()

    if args.list:
        for key, scenario in SCENARIOS.items():
            print(f"  {key:<10} {scenario['title']}")
        return 0

    keys = args.only or list(SCENARIOS)
    unknown = [k for k in keys if k not in SCENARIOS]
    if unknown:
        print(f"Unknown scenario(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(SCENARIOS)}")
        return 2

    runner = build_runner("marketing_demo")

    for key in keys:
        try:
            await run_scenario(runner, key, SCENARIOS[key])
        except Exception as exc:  # keep going so one failure does not end the demo
            print(f"\n  Scenario {key!r} failed: {type(exc).__name__}: {exc}")

    decks = sorted((ROOT / "output/decks").glob("*.pptx")) \
        if (ROOT / "output/decks").exists() else []
    if decks:
        print(f"\nDecks written: {', '.join(d.name for d in decks)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
