"""ADK Web entry. "adk web agents" imports "root_agent" from this module."""

import agents.runtime_env  # noqa: F401 — env must load before agents build
from agents.orchestrator.agent import root_agent

__all__ = ["root_agent"]
