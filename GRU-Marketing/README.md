# GRU Marketing

A proof of concept: seven marketing orchestrators under one Google ADK root,
with a marketer-facing workspace branded as **James**. The browser shell
follows the RevOps workspace (landing, dashboard, chat). Chat still hits this
repo's marketing FastAPI app and root router — not RevOps specialists.

All seven domain orchestrators run in one process on a shared sample dataset.

## Workspace

```bash
python -m ui
```

Open http://127.0.0.1:8080.

| Path | Page |
| --- | --- |
| `/` | Landing |
| `/dashboard` and `/app` | Dashboard (book of programs) |
| `/chat` | Chat workspace |

The chrome uses RevOps filter names: geo, boat, opp, report, size, stage, time.
Python maps those onto marketing data (`ui/catalog.py`, `ui/dashboard.py`,
`ChatFilters` in `ui/app.py`). `/api/chat` streams from the marketing
orchestrator. Named chat collections live in the sidebar.

## Why this shape

The system is a tree of agents, not a single prompt. A request like "how is
pipeline looking" goes through the root, then the Analysis team, then a
specialist that actually has the tools. That sounds like overhead until you
notice the alternative: one agent with thirty tools, guessing which to call.

Two rules make the answers trustworthy:

1. **No arithmetic in the model.** Every number is computed in Python
   (`packages/mktg_core/metrics/`) and handed to the agent as a finished
   table. The agent explains it. This is the difference between a demo that
   survives a stakeholder checking a number they already know, and one that
   does not.
2. **Routing is the descriptions.** ADK picks a sub-agent by reading its
   `description`. Those strings are code, and
   `evals/routing.evalset.json` exists to keep them honest.

The rest of the design is in [CONVENTIONS.md](CONVENTIONS.md). Read that
before adding an agent.

## What is in each orchestrator

**Analysis** — campaign performance, recommendations, pipeline health,
asset influence, and two deck builders that emit a PowerPoint file.

**Regional Events** — where to run an event, who to invite, account briefs
(written in parallel) and pipeline in the room.

**Marketing Ops** — Salesforce campaign creation, 6sense segments, Marketo
deploy, and a four-step list load that is a `SequentialAgent` because the
order is a requirement, not a suggestion.

**Campaign Design** — campaign ideation, brief builder, competitive
battlecards.

**ABM** — account tiering, intel briefs, gap/value mapping, persona
messaging, and multi-channel packages (email CSV, LinkedIn, Folloze, playbook).

**Content Generation** — anchor assets, localization, asset grids, and
campaign-variant packages.

**Brand** — social sentiment, share of voice, news trends, rapid-response
campaign packages.

The sample dataset ("dummy data") lives in the top-level `dummy_data/` folder
and is one consistent world: the same accounts appear in the pipeline analysis,
the event attendee list and the Marketo load. Six stories are planted in it so
the agents have something real to say. The current operating user is
`dummy_data/me.json` (Omkar Patil, Senior Marketing Manager) — agents default
the campaign owner and "my region" to this person. Regenerate everything with
`python scripts/generate_fixtures.py`.

## Setup

Python 3.10–3.13. 3.12 is what this was built against.

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

The agents need a Gemini model. Either:

```bash
export GOOGLE_API_KEY=...                  # AI Studio
```

or:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE      # Vertex AI
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_CLOUD_LOCATION=us-central1
```

The default model is `gemini-3.6-flash`. Override with `MKTG_MODEL` if you
need a different one.

### Remote BattleCard agent

Campaign design's competitive battlecard specialist is a remote A2A agent,
resolved from the Google Cloud Agent Registry (`us-west1`). It needs
Application Default Credentials and a project:

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project    # defaults to adk-ai-interns
export BATTLECARD_AGENT_ID=agentregistry-... # the registry id for the agent
```

If credentials or the registry are unavailable, the app still starts; campaign
design just runs without the battlecard specialist. You do not need to set
`GOOGLE_GENAI_USE_VERTEXAI` for this: the registry authenticates through ADC
independently of the model auth above.

## Run

The tests need no model and no network. They are the ones that catch the
failures that are silent rather than loud: a state key the template engine
will not substitute, a write tool that has crept into a read-only
orchestrator, a calculation that drifted from the fixtures, or UI markup that
no longer matches the RevOps pages we serve.

```bash
uv run pytest
```

A live demo against the real root orchestrator:

```bash
uv run python scripts/demo.py
uv run python scripts/demo.py --only abm
uv run python scripts/demo.py --list
```

The developer ADK UI, pointing at the root:

```bash
adk web
```

Pick the `root` app in the UI. You can also pass the folder explicitly:

```bash
adk web root
```

The routing evalset, 42 prompts including the ones that sound like they
could belong to either half of the system. Re-run this whenever a
description changes. A full run transfers into the specialists, so it
takes several minutes and needs a live model:

```bash
python scripts/run_routing_evals.py
python scripts/run_routing_evals.py --case amb-01
```

## Layout

```
packages/mktg_core/          shared library
  contracts/                 the data shapes
  connectors/                one interface per source system, plus fakes
  metrics/                   all the arithmetic
  rendering/                 DeckSpec -> .pptx, artifacts -> md/csv
agents/                      seven domain agents, each with prompts.py
  analysis/
  regional_events/
  marketing_ops/
  campaign_design/
  abm/
  content_generation/
  brand/
tools/                       ADK tools, one folder per agent
dummy_data/                  one shared sample dataset
root/                        the top-level router
ui/                          James workspace (python -m ui)
  catalog.py                 marketing rows + RevOps filter mapping
  dashboard.py               dashboard payloads
  app.py                     FastAPI, ChatFilters, /api/chat
evals/routing.evalset.json
scripts/demo.py
```

Swapping the sample data for a live Salesforce or Marketo is a change of
`MKTG_DATA_SOURCE`, not a rewrite of any agent. The live connectors are not
built yet; they fail loudly if that env var is set.

## What is not here

RBAC, PII handling, write approvals, prompt-injection defence and
observability are all deferred. They become necessary the day this system
touches real data, and not before. The connector interface is the one
thing carried forward from that list, because it is what makes the swap a
config change.
