"""The runnable app.

Scripts should build the runner from here rather than passing the bare agent,
so they all get the same configuration.

The reason this file exists at all is context caching. Routing a request
through this system means two or three agent transfers, and every transfer
swaps the system instruction and the tool set. Without a cache config that
changes the request prefix each time, so the entire prompt is re-sent and
re-billed after each hop. On a seven-orchestrator tree that is the single
largest avoidable cost.
"""

from __future__ import annotations

from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps import App
from google.adk.plugins.global_instruction_plugin import GlobalInstructionPlugin
from google.adk.runners import InMemoryRunner

from .agent import REPLY_CONTRACT, marketing_orchestrator


def build_app(name: str = "marketing_agents") -> App:
    return App(
        name=name,
        root_agent=marketing_orchestrator,
        # The reply contract has to reach every specialist, because the agent
        # that answers is whichever one the router transferred to, not this
        # one. A plugin prepends it to all of them from a single place, which
        # beats pasting the same block into twenty-eight prompts.
        plugins=[GlobalInstructionPlugin(REPLY_CONTRACT)],
        context_cache_config=ContextCacheConfig(
            # Half an hour comfortably covers a demo or a working session.
            ttl_seconds=1800,
            cache_intervals=10,
        ),
    )


def build_runner(name: str = "marketing_agents") -> InMemoryRunner:
    """In-memory sessions are right for the POC: nothing needs to outlive a run."""
    return InMemoryRunner(app=build_app(name))
