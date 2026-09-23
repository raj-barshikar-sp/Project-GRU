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

# The routers (the marketing root and the team coordinators) do no marketing
# work; they only pick who runs next. Routing accuracy is more sensitive to the
# model than the specialists are, since the specialists mostly summarise tables
# that Python already computed. Point the routers at a stronger model with
# MKTG_ROUTER_MODEL when a demo needs steadier routing; it defaults to the
# shared model so nothing changes unless the env var is set.
ROUTER_MODEL = os.environ.get("MKTG_ROUTER_MODEL", DEFAULT_MODEL)


def router_generate_config() -> types.GenerateContentConfig:
    """Deterministic generation for the routers.

    A router that samples can send the same request to different teams on
    different runs. Temperature 0 makes routing repeatable, which is what the
    evalset assumes; the specialists keep the model default so their prose does
    not read as flat.
    """
    return types.GenerateContentConfig(temperature=0.0)


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
