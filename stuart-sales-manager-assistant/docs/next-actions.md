# Next actions

Keep the architecture: **planner → JSON-grounded specialists → conversational
writer**. The manager never selects a specialist.

## Product direction

1. Keep the linked JSON fixtures as the source of truth while specialist
   contracts stabilize.
2. Expand routing evals for cross-team asks and explicit follow-ups.
3. Replace `source_context()` with production connectors when the local
   snapshot flow is stable.

## Definition of done for each specialist

- `mode="single_turn"`, transfer disabled, and a typed output schema.
- No tools; the workflow injects only the specialist's owned source snapshots.
- Registry entry, task-menu ownership, and progress copy.
- Synthesis remains last and never exposes internal agent or source names.
- Unit tests plus at least one routing-eval case.
