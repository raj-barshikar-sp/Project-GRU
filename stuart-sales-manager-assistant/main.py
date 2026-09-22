"""Sales Manager assistant entry point.

The sales manager only chats with the orchestrator. From the project root:

    pip install -r requirements.txt
    python -m ui

Open http://127.0.0.1:8080. Optional ADK debug UI: `adk web agents`.
"""

from __future__ import annotations

import agents.runtime_env  # noqa: F401 — load Vertex quota + ADK flags first
from agents.orchestrator.agent import root_agent

__all__ = ["root_agent"]
