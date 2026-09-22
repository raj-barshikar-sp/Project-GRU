"""Shared constants for Stuart's agents."""

import os

from google.genai import types

GEMINI_MODEL = os.getenv("STUART_MODEL", "gemini-3.6-flash")
SYNTHESIS_MODEL = os.getenv(
    "STUART_SYNTHESIS_MODEL", "gemini-3.6-flash"
)
CHILD_TIMEOUT_SECONDS = float(
    os.getenv("STUART_CHILD_TIMEOUT_SECONDS", "90")
)

# Stuart writes his own conversational replies. This is only used when the
# planner call itself fails, so the manager never sees an empty turn.
FALLBACK_REPLY = (
    "I lost that one on my side — say it again and I'll pick it up."
)

# Specialists read supplied snapshots; low temperature keeps facts stable.
SAFE_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.2,
    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
)

SYNTHESIS_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
)

# The planner both routes and speaks, so it needs room to vary its wording.
PLANNER_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.6,
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
)
