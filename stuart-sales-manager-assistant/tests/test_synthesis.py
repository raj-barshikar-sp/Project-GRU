"""Stuart's final writer is structured and no-tool."""

from agents.synthesis.agent import synthesis_agent
from agents.synthesis.prompt import SYNTHESIS_INSTRUCTION
from models.synthesis_output import SynthesisOutput


def test_final_writer_contract() -> None:
    assert synthesis_agent.name == "synthesis"
    assert synthesis_agent.tools == []
    assert synthesis_agent.output_schema is SynthesisOutput
    assert all(
        heading in SYNTHESIS_INSTRUCTION
        for heading in ("ROLE", "PERSONA", "OBJECTIVE", "INSTRUCTIONS", "GUARDRAILS")
    )


def test_final_writer_fills_every_briefing_section() -> None:
    prompt = SYNTHESIS_INSTRUCTION
    assert all(
        field in prompt for field in ("summary:", "insights:", "actions:", "artifacts:")
    )
    assert "Never claim there are no records" in prompt
    assert "Leave a list empty rather than filling it" in prompt
