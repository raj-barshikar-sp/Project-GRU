"""One place to change the model every agent uses."""

from __future__ import annotations

import os

from google.adk.planners import BuiltInPlanner
from google.genai import types

# Flash is the right default here: the reasoning agents are summarising tables
# that were computed in Python, which is not a hard reasoning task, and routing
# across seven orchestrators benefits far more from low latency than from a
# larger model.
#
DEFAULT_MODEL = os.environ.get("MKTG_MODEL", "gemini-3.6-flash")


def thinking_planner() -> BuiltInPlanner:
    """Ask the model to hand back its thought summaries.

    Gemini keeps thinking to itself unless it is told otherwise, so without
    this the chat stream has no `thought` parts to forward and the Thinking
    panel opens onto nothing. A fresh planner per agent, because ADK stores it
    on the agent.
    """
    return BuiltInPlanner(
        thinking_config=types.ThinkingConfig(include_thoughts=True)
    )
