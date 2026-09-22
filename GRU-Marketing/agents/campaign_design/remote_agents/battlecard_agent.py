"""Remote BattleCard agent, resolved from the Google Cloud Agent Registry.

This is the competitive battlecard specialist for campaign design. Unlike the
in-process sub-agents, it lives behind an A2A boundary and is deployed
elsewhere. We resolve it through the same Agent Registry the A2A Testing repo
uses, then stamp the human-authored name and description from
``battlecard_agent_card.json`` onto it. That local card is what the campaign
design orchestrator reads to decide, in context, when to route here.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx

from .google_auth import GoogleAuth

logger = logging.getLogger(__name__)

# Agent Registry is regional. Keep this location independent of any global
# Gemini location the marketing models use.
DEFAULT_PROJECT_ID = "adk-ai-interns"
REGISTRY_LOCATION = "us-west1"

# Supplied per environment. The BattleCard agent's registry id lives here so it
# can be swapped without touching code.
AGENT_ID = os.environ.get("BATTLECARD_AGENT_ID", "<battlecard-agent-id>")

AGENT_CARD_PATH = Path(__file__).with_name("battlecard_agent_card.json")


def load_agent_card() -> dict:
    """The local agent card: what ADK reads before invoking the remote agent."""
    return json.loads(AGENT_CARD_PATH.read_text())


def project_id() -> str:
    return os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT_ID)


def agent_resource_name(project: str | None = None) -> str:
    pid = project or project_id()
    return f"projects/{pid}/locations/{REGISTRY_LOCATION}/agents/{AGENT_ID}"


def build_httpx_client(timeout_seconds: float = 60.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        auth=GoogleAuth(), timeout=httpx.Timeout(timeout_seconds)
    )


def build_battlecard_agent(
    *,
    project: str | None = None,
    registry=None,
    httpx_client: httpx.AsyncClient | None = None,
):
    # Imported lazily: the registry integration pulls heavy Google Cloud
    # dependencies that need not be installed just to import the marketing app.
    from google.adk.integrations.agent_registry import AgentRegistry

    pid = project or project_id()
    registry = registry or AgentRegistry(
        project_id=pid, location=REGISTRY_LOCATION
    )
    httpx_client = httpx_client or build_httpx_client()
    agent = registry.get_remote_a2a_agent(
        agent_name=agent_resource_name(pid),
        httpx_client=httpx_client,
    )

    # Route on the human-authored card, not on whatever the registry happens to
    # return. Name and description are what the LlmAgent orchestrator matches.
    card = load_agent_card()
    agent.name = card["name"]
    agent.description = card["description"]
    return agent


def _build_or_none():
    """Build at import, but never take the whole app down over credentials.

    The marketing app imports all seven orchestrators at startup. Resolving the
    remote agent needs Application Default Credentials and a reachable registry;
    if those are missing (local dev, CI without secrets), skip the sub-agent
    rather than crash the import.
    """
    try:
        return build_battlecard_agent()
    except Exception as exc:  # noqa: BLE001 - import must not fail
        logger.warning(
            "BattleCard remote agent unavailable, skipping it as a sub-agent: %s",
            exc,
        )
        return None


battlecard_agent = _build_or_none()
