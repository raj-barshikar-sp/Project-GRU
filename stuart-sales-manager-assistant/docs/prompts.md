# Agent prompt contracts

Every LLM prompt uses the same five sections:

1. **Role** — what the agent owns.
2. **Persona** — how it reasons and communicates.
3. **Objective** — the outcome for this turn.
4. **Instructions** — how to use its supplied context.
5. **Guardrails** — what it must not infer or expose.

`route_planner` interprets natural language rather than matching phrases.
Typos, shorthand, and follow-ups are normal input. It returns either a legal
specialist set or a conversational `direct_reply`.

Specialists receive the manager message, working context, and raw source JSON.
They return `SpecialistReport`; they never address the manager directly.

`synthesis` receives the reports and returns one `SynthesisOutput`: summary,
insights, actions, and artifacts. The workflow renders it as `## Summary`,
`## Key Insights`, `## Recommended Actions`, and `## Artifacts`, which the UI
parses back into briefing cards. Direct planner replies stay plain text.
