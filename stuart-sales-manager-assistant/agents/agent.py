"""ADK Web entry — the only app the AE chats with is the orchestrator."""

import agents.runtime_env  # noqa: F401 — load Vertex quota + ADK flags first
from agents.orchestrator.agent import root_agent

__all__ = ["root_agent"]
