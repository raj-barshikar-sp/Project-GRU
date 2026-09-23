---
name: ponytail
description: Working method for the entire GRU Marketing codebase (Python agents, tools, catalog, FastAPI, and UI). Use on every GRU Marketing change: keep the marketing orchestrator, James branding only, marketing filter names in HTML/JS/Python, do not revive the old Marketing Minion shell.
---

# Ponytail (GRU Marketing)

Apply this skill to every file in this repo. Do not treat it as UI-only.

## Source of truth

- The browser UI is the James marketing workspace: landing, dashboard, chat. Keep it marketing-native. Do not rebuild a parallel frontend.
- Brand is James: `james.png`, `askJames`, `/api/chat` hits this marketing FastAPI app.
- Marketing agents, tools, contracts, and SSE stay in this repo.

## Do not restore

Dual rails, workbench, projects, compare, starter strips in HTML, `motion.js`, composer task chips, accounts dialog. Do not reintroduce sales chrome (opps, boats, deal desk, OTC, opp size, pipeline stage) in the UI.

## Filters

Marketing filter names, used the same way in HTML, JS, and Python: campaigns, campaign types, asset types, content, events, accounts, geo, spend, time.

They live in `ui/catalog.py`, `ui/dashboard.py`, and `ui/app.py` `ChatFilters`.

## Pages

`/` landing → `/dashboard` (and `/app`) → `/chat`.

## Tests

Assert the marketing DOM and JS that is actually served. Keep backend SSE / `parse_reply` / scope tests. Do not pin old Marketing Minion function names.

## Code

Match existing Python style in the file you touch. Keep HTML/JS/Python filter names in sync rather than adding compatibility aliases.
