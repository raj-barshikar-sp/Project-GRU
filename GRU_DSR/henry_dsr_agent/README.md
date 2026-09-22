# Henry the DSR Minion

Henry is a local-first digital sales representative copilot for account prioritization, discovery, outreach, competitive positioning, and deal-risk review. It combines typed CRM and intent data with deterministic specialist agents, then presents the result through a responsive dashboard, HTTP API, or terminal.

No cloud model or API key is required. The included repositories read local JSON, latency is simulated, scoring is explainable, and the same orchestrator powers every interface.

## Quick start

Python 3.10 or newer is required.

```bash
cd /path/to/GRU_DSR
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "./henry_dsr_agent[dev]"
cp henry_dsr_agent/.env.example henry_dsr_agent/.env
henry serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Interactive API documentation is at `/docs`, and the OpenAPI document is at `/openapi.json`.

### CLI

```bash
# Interactive conversation (type exit to finish)
henry chat

# One question
henry chat "Which accounts deserve attention today?"

# Explicit workflows
henry workflow prospecting --message "Rank my enterprise accounts"
henry workflow discovery --account 001APEXFIN000001 --message "Prepare tomorrow's call"
henry workflow outreach --account 001APEXFIN000001 --context '{"persona":"CISO"}'
henry workflow deal-risk --account 001APEXFIN000001
```

Run without installing the script with `python -m henry_dsr_agent.cli`.

## Dashboard

The dashboard keeps three kinds of context visible:

- **DSR Ask catalog:** all 26 local actions across coaching, prospecting, customer
  expansion, qualification, advancement, close, and FAQ categories.
- **Workflows:** prospecting, discovery, outreach, and deal-risk missions.
- **Henry workspace:** interactive chat, suggested actions, and readable rendered output.
- **Rep workspace:** selected account context, opportunities, and immediate tasks.

It uses plain HTML, CSS, and JavaScript with no CDN or frontend build step. Account selection is passed into every subsequent workflow request.

Document-oriented actions such as quote, proposal, contract review, commission,
and rules of engagement are explicitly labeled local demo guidance. They derive
only from the bundled account fields and never claim access to production policy,
pricing, contracts, or external systems.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service readiness |
| `GET`, `POST` | `/api/territories` | List or inspect territory context |
| `GET`, `POST` | `/api/accounts` | List or filter accounts |
| `POST` | `/api/prospecting` | Prioritize prospects |
| `POST` | `/api/discovery` | Prepare a discovery brief |
| `POST` | `/api/outreach` | Build account-specific outreach |
| `POST` | `/api/deal-risk` | Assess opportunity risk |
| `POST` | `/api/ask` | Execute one of the complete DSR catalog actions |
| `GET` | `/api/ask-catalog` | List supported action metadata |
| `POST` | `/api/chat` | Send a general request to Henry |

Workflow endpoints accept a flexible envelope:

```json
{
  "message": "Draft a concise note for the CISO",
  "account_id": "001APEXFIN000001",
  "territory_id": "west-enterprise",
  "context": {
    "persona": "CISO",
    "tone": "direct"
  }
}
```

Example calls:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/accounts
curl -X POST http://127.0.0.1:8000/api/prospecting \
  -H 'Content-Type: application/json' \
  -d '{"message":"Show my top three accounts","context":{}}'
curl -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What should I do next?","context":{}}'
```

Successful workflow responses have a stable outer shape:

```json
{"workflow": "prospecting", "result": {"accounts": []}}
```

Input validation errors return HTTP 422. Unavailable workflows return 501, and unexpected execution failures return a sanitized HTTP 500 response.

## Architecture

```text
Dashboard / CLI / HTTP clients
            │
        FastAPI API
            │
     HenryOrchestrator
            │
   dependency StateGraph
     ┌──────┼────────┐
 account  intent  competitive/outreach/risk agents
     └──────┼────────┘
       typed repositories
            │
       local JSON data
```

Pydantic v2 models are the contracts at data and workflow boundaries. Specialist agents remain independently testable. The state graph supports synchronous and asynchronous nodes, runs dependency-ready branches concurrently, and rejects conflicting parallel state updates.

## Configuration

Copy `.env.example` when you want to override defaults. Current runtime settings are:

- `HENRY_DATA_DIR`: directory containing mock JSON sources.
- `HENRY_MOCK_LATENCY_MS`: baseline repository latency in milliseconds.
- `HENRY_MOCK_LATENCY_JITTER_MS`: random additional latency in milliseconds.
- `HENRY_HOST` and `HENRY_PORT`: convenient values for scripts; pass matching `--host` and `--port` options to `henry serve`.

Configuration and data remain on the machine. The API binds to loopback by default and CORS is restricted to the local dashboard origins.

## Development

```bash
pytest
ruff check .
mypy .
```

The suite covers schema normalization and rejection cases, typed repository behavior, deterministic scoring, graph/orchestrator state behavior, API routing, and static presentation. Test fixtures use temporary local data and do not require network access.

## Local-first guarantees

- No external JavaScript, fonts, analytics, or CDNs.
- No credentials are needed for the default experience.
- Mock enterprise data is validated before use and cached in-process.
- Deterministic scores include factor-level contributions and rationale.
- HTTP requests and CLI commands call the same orchestrator contract.

Treat included data as demonstration data. Do not place production credentials or sensitive customer exports in the repository.
