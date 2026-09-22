---
name: ponytail
description: Working method for the entire GRU Marketing codebase (Python agents, tools, catalog, FastAPI, and UI). Use on every GRU Marketing change: port RevOps UI from main, keep the marketing orchestrator, James branding only, map filters in Python, do not revive the old Marketing Minion shell.
---

# Ponytail (GRU Marketing)

Apply this skill to every file in this repo. Do not treat it as UI-only.

## Source of truth

- Browser UI comes from `https://github.com/samihan-narayankeri-sp/project-gru-revops-poc` **`main`**. Copy the static shell. Do not rebuild a parallel marketing frontend.
- Allowed edits on copied UI: Bob → James, `bob.png` → `james.png`, `askBob` → `askJames`, `/api/chat` still hits this marketing FastAPI app.
- Marketing agents, tools, contracts, and SSE stay in this repo. Do not replace them with RevOps specialists.

## Do not restore

Dual rails, workbench, projects, compare, starter strips in HTML, `motion.js`, composer task chips, accounts dialog, marketing-only filter IDs in HTML (`filter-campaigns`, `open-accounts`).

## Filters

RevOps chrome names: geo, boat, opp, report, size, stage, time.

Map those onto marketing data in Python (`ui/catalog.py`, `ui/dashboard.py`, `ui/app.py` `ChatFilters`). Add aliases on catalog rows if the copied JS reads `territory` / `owner`.

## Pages

`/` landing → `/dashboard` (and `/app`) → `/chat`.

## Tests

Assert the RevOps DOM and JS that is actually served. Keep backend SSE / `parse_reply` / scope tests. Do not pin old Marketing Minion function names.

## Code

Match existing Python style in the file you touch. Prefer mapping and aliases over rewriting copied `app.js` / `dashboard.js` unless a placeholder (`{region}`) cannot bind otherwise.
