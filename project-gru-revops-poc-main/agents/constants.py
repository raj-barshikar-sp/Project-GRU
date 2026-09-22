"""Model names, timeouts, and shared GenerateContentConfig for agents."""

import os

from google.genai import types

GEMINI_MODEL = os.getenv("SELLER_COPILOT_MODEL", "gemini-3.6-flash")
SYNTHESIS_MODEL = os.getenv(
    "SELLER_COPILOT_SYNTHESIS_MODEL", "gemini-3.6-flash"
)
TOOL_LATENCY_SECONDS = float(
    os.getenv("SELLER_COPILOT_MOCK_LATENCY_SECONDS", "0")
)
CHILD_TIMEOUT_SECONDS = float(
    os.getenv("SELLER_COPILOT_CHILD_TIMEOUT_SECONDS", "90")
)
TASK_AGENT_IDS = (
    "revops_forecast",
    "revops_quoting",
    "revops_reporting",
    "revops_hygiene",
    "revops_otc",
    "revops_pricing",
)

# Keep thinking minimal on Flash specialists so tool calls stay well-formed.
SAFE_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.2,
    thinking_config=types.ThinkingConfig(
        thinking_level="MINIMAL",
        include_thoughts=True,
    ),
)

SYNTHESIS_GEN_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    thinking_config=types.ThinkingConfig(
        thinking_level="MEDIUM",
        include_thoughts=True,
    ),
)
