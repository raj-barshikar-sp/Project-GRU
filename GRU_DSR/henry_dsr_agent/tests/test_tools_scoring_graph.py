import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from henry_dsr_agent.agents.intent_scorer import IntentScorerAgent
from henry_dsr_agent.config.settings import Settings
from henry_dsr_agent.orchestrator.graph import StateGraph
from henry_dsr_agent.tools.repository import JsonRepository, RepositoryError
from pydantic import BaseModel


class Record(BaseModel):
    id: int
    name: str


def test_json_repository_validates_caches_and_clears(tmp_path: Path) -> None:
    source = tmp_path / "records.json"
    source.write_text('[{"id": 1, "name": "first"}]', encoding="utf-8")
    repository = JsonRepository(
        "records.json",
        Record,
        settings=Settings(data_dir=tmp_path, mock_latency_ms=0, mock_latency_jitter_ms=0),
    )
    assert repository.all()[0].name == "first"
    source.write_text('[{"id": 1, "name": "changed"}]', encoding="utf-8")
    assert repository.all()[0].name == "first"
    repository.clear_cache()
    assert repository.all()[0].name == "changed"


@pytest.mark.parametrize(
    ("content", "message"),
    [("{bad json", "invalid JSON"), (json.dumps([{"id": "bad"}]), "schema validation")],
)
def test_json_repository_wraps_source_errors(
    tmp_path: Path, content: str, message: str
) -> None:
    (tmp_path / "records.json").write_text(content, encoding="utf-8")
    repository = JsonRepository(
        "records.json",
        Record,
        settings=Settings(data_dir=tmp_path, mock_latency_ms=0, mock_latency_jitter_ms=0),
    )
    with pytest.raises(RepositoryError, match=message):
        repository.all()


def test_repository_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="simple"):
        JsonRepository("../records.json", Record)


@pytest.mark.asyncio
async def test_intent_score_is_weighted_and_explainable() -> None:
    result = await IntentScorerAgent().run(
        intent={"score": 90, "buying_stage": "evaluation"},
        account={
            "industry": "Technology",
            "employee_count": 2000,
            "annual_revenue": 1_000_000,
            "territory": "West",
            "last_activity_date": datetime.now(timezone.utc) - timedelta(days=3),
        },
    )
    assert result.score == round(sum(factor.contribution for factor in result.factors), 1)
    assert result.priority == "high"
    assert {factor.name for factor in result.factors} == set(IntentScorerAgent.WEIGHTS)
    assert "strongest factor" in result.rationale


@pytest.mark.asyncio
async def test_state_graph_merges_dependencies_and_parallel_nodes() -> None:
    order: list[str] = []

    async def seed(state: dict[str, object]) -> dict[str, int]:
        await asyncio.sleep(0)
        order.append("seed")
        return {"seed": 2}

    graph = StateGraph().add_node("seed", seed)
    graph.add_parallel(
        {
            "double": lambda state: {"double": int(state["seed"]) * 2},
            "triple": lambda state: {"triple": int(state["seed"]) * 3},
        },
        after="seed",
    )
    result = await graph.run({"request": "rank"})
    assert result == {"request": "rank", "seed": 2, "double": 4, "triple": 6}
    assert order == ["seed"]


@pytest.mark.asyncio
async def test_state_graph_rejects_conflicting_parallel_updates() -> None:
    graph = StateGraph().add_parallel(
        {"one": lambda _: {"score": 1}, "two": lambda _: {"score": 2}}
    )
    with pytest.raises(ValueError, match="conflicting"):
        await graph.run()


@pytest.mark.asyncio
async def test_state_graph_detects_cycles() -> None:
    graph = StateGraph().add_node("one", lambda _: {}).add_node("two", lambda _: {})
    graph.add_edge("one", "two").add_edge("two", "one")
    with pytest.raises(ValueError, match="cycle"):
        await graph.run()
