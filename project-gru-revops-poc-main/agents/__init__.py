"""Seller Co-Pilot ADK package.

Layout:
- "agent": ADK Web entry; exports "root_agent".
- "orchestrator": planner, domain routers, and the code-owned workflow.
- "specialists": one package per RevOps domain (tools, prompt, agent).
- "synthesis": writes the AE-facing markdown reply.
- "data": mock CRM, dummy JSON tables, and RevOps query helpers.
- "session_memory": "last_account" and related keys on session state.
"""
