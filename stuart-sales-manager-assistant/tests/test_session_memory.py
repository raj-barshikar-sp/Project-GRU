"""Session memory for AE, last account, and territory."""

from __future__ import annotations

from types import SimpleNamespace

from agents.orchestrator.agent import root_agent
from agents.orchestrator.prompt import build_orchestrator_instruction
from agents.session_memory import (
    apply_working_context,
    detect_account_in_text,
    detect_territory_in_text,
    seed_context_from_text,
    seed_session_state,
)


def test_detect_account_and_territory() -> None:
    assert (
        detect_account_in_text("Prep me for Acme Financial tomorrow")
        == "Acme Financial"
    )
    assert (
        detect_account_in_text("Horizon BioPharma hygiene")
        == "Horizon BioPharma"
    )
    assert detect_account_in_text("hello there") is None
    assert detect_territory_in_text("rank the west book") == "west"
    assert detect_territory_in_text("hello there") is None
    assert detect_territory_in_text("no region named") is None


def test_apply_working_context_sets_owner_and_territory() -> None:
    state: dict[str, str] = {}
    remembered = apply_working_context(state, account="Acme Financial")
    assert remembered["last_account"] == "Acme Financial"
    assert remembered["ae_name"] == "Elena Rodriguez"
    assert remembered["last_territory"] == "east"


def test_seed_session_state_fills_empty_keys() -> None:
    ctx = SimpleNamespace(state={})
    seed_session_state(ctx)
    assert ctx.state == {
        "ae_name": "",
        "last_account": "",
        "last_territory": "",
        "last_opportunity": "",
    }
    ctx.state["last_account"] = "Acme Corp"
    seed_session_state(ctx)
    assert ctx.state["last_account"] == "Acme Corp"


def test_seed_context_from_text_runs_before_routing() -> None:
    state: dict[str, str] = {}
    remembered = seed_context_from_text(
        state, "What should I send Elena at Meridian Bank?"
    )
    assert remembered["last_account"] == "Meridian Bank"
    assert remembered["ae_name"] == "Elena Rodriguez"
    assert remembered["last_territory"] == "east"


def test_planner_instruction_documents_direct_specialist_contract() -> None:
    instruction = build_orchestrator_instruction()
    assert "working_context" in instruction
    assert "crm_intelligence_specialist" in instruction
    assert root_agent.name == "central_orchestrator"
