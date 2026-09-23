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
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions import BaseSessionService

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


def build_runner(
    name: str = "marketing_agents",
    *,
    session_service: BaseSessionService | None = None,
) -> Runner:
    """Build the runner from the shared app so every entry point gets the same
    context cache and reply-contract plugin instead of wiring its own.

    In-memory sessions are the POC default: nothing needs to outlive a run, and
    a process restart starting from a clean slate is acceptable here. That does
    mean chats and session context are lost on restart; pass a persistent
    ``session_service`` to swap in a durable backend without duplicating any of
    the app wiring above.
    """
    app = build_app(name)
    if session_service is None:
        return InMemoryRunner(app=app)
    return Runner(app=app, session_service=session_service)
