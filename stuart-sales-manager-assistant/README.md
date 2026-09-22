# Stuart — Sales Manager Assistant

Stuart is a conversational Google ADK assistant for a Sales Manager.

## Flow

```text
Manager
  → route_planner
  → one or more JSON-grounded specialists
  → synthesis
  → Stuart's reply
```

Gemini decides the route on every turn. There are no keyword routers and no
specialist tools. The workflow injects only the local JSON snapshots each
specialist owns:

| Agent | Data |
|---|---|
| `crm_intelligence_specialist` | Salesforce + stage policy |
| `activity_engagement_specialist` | Salesforce + Gong + calendar/email |
| `rep_performance_specialist` | Salesforce + Gong + Workday |
| `forecast_modeling_specialist` | Salesforce + Gong + stage policy |
| `knowledge_base_rag` | Confluence knowledge snapshot |

Every LLM agent defines a role, persona, objective, instructions, and
guardrails. Specialists return grounded reports; `synthesis` merges them into a
briefing of summary, insights, actions, and artifacts, which the UI renders as
cards. Planner small talk and clarifications stay plain text.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m ui
```

For ADK Web, run from the project root:

```bash
adk web agents
```

If ADK Web was already open during an agent rename, stop it and start it again.
The current root is `central_orchestrator`; its visible children are
`route_planner`, the five specialists above, and `synthesis`.

## Verify

```bash
pytest -q
python scripts/run_routing_eval.py
```
