# Stuart architecture

`central_orchestrator` is a small workflow boundary around Gemini:

```text
Sales Manager → route_planner ─┬─ crm_intelligence_specialist
                               ├─ activity_engagement_specialist
                               ├─ rep_performance_specialist
                               ├─ forecast_modeling_specialist
                               └─ knowledge_base_rag
                                             ↓
                                         synthesis
                                             ↓
                                      Stuart's response
```

The planner owns intent, follow-ups, clarifying questions, and casual chat.
Code only validates its selected IDs, injects the right data, and runs selected
specialists concurrently.

## Data boundary

`agents/data_context.py` maps each specialist to the raw snapshots it may read.
The files are read on every turn, so changing a snapshot does not require
clearing an application cache. No specialist has ADK tools.

This local JSON injection is the temporary data-access layer. Replace
`source_context()` with production connectors when real systems are available;
agent prompts and orchestration do not need to change.

## Conversation

The planner and writer are separate:

- `route_planner` never states business facts.
- Specialists interpret only their supplied records.
- `synthesis` never sees raw source files; it receives grounded specialist
  reports and writes Stuart's final response.

This keeps casual turns natural while preventing the conversational agent from
inventing CRM or policy facts.
