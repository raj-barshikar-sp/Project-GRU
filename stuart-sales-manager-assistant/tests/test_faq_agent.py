"""Knowledge specialist reads the local approved snapshot directly."""

from agents.data_context import source_context
from agents.knowledge_base_rag.agent import knowledge_base_rag_agent


def test_knowledge_agent_is_no_tool_and_confluence_grounded() -> None:
    assert knowledge_base_rag_agent.tools == []
    assert knowledge_base_rag_agent.output_schema.__name__ == "SpecialistReport"
    context = source_context("knowledge_base_rag")
    assert "CONF-DOC-001" in context
    assert "CONF-DOC-005" in context
