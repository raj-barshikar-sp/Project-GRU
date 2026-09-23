"""Prompt fragments shared by the team orchestrators.

Every team now calls its specialists as AgentTools, so a specialist reply comes
back to the orchestrator instead of being sent straight to the user. The reply
is already contract-shaped, because the global reply contract reaches every
agent, so a single-specialist answer should be handed back untouched. Only a
request that genuinely spans several specialists needs assembling.
"""

from __future__ import annotations

PASS_THROUGH_RULE = """
When you called only one specialist and its result already starts with a
reply-contract heading such as ## Summary, ## Receipt, ## Question, or
## Cannot, return that result verbatim. Do not introduce it, summarise it,
rewrite it, or change its numbers. Only assemble a new answer when several
specialist results must be combined to satisfy the request.
""".strip()
