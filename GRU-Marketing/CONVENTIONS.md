# Shared repo conventions

Both halves of the Marketing Agents system live in this one repo and run in one
process. That removes deployment coordination but replaces it with code
coordination, so these five rules exist. Read this before writing an agent.

Owner split: **Mangesh** owns Analysis, Regional Events, Marketing Ops.
**Omkar** owns Campaign Design, ABM, Content Generation, Brand. All seven
orchestrators are now implemented in this repo.

---

## 1. Folder ownership

You may edit your own agent folders freely, without review:

| Folder                              | Owner    |
| ----------------------------------- | -------- |
| `agents/analysis/` + `tools/analysis/` | Mangesh  |
| `agents/regional_events/` + `tools/regional_events/` | Mangesh  |
| `agents/marketing_ops/` + `tools/marketing_ops/` | Mangesh  |
| `agents/campaign_design/` + `tools/campaign_design/` | Omkar |
| `agents/abm/` + `tools/abm/` | Omkar |
| `agents/content_generation/` + `tools/content_generation/` | Omkar |
| `agents/brand/` + `tools/brand/` | Omkar |

These are shared. Give the other person a heads-up before changing them:

- `packages/mktg_core/` — data shapes, connectors, metrics, rendering
- `tools/_shared/` — helpers used by more than one domain
- `root/agent.py` — the top-level router
- `evals/` — the routing test set
- `dummy_data/` — the sample dataset (regenerate with
  `python scripts/generate_fixtures.py`). `dummy_data/me.json` is the current
  operating user (Omkar Patil, Senior Marketing Manager); agents default the
  campaign owner and "my region" to this person via `get_current_user`.

Rule of thumb: if a change to `mktg_core` would alter an existing function's
signature or a model's field, mention it. Adding something new is fine.

## 2. Agent naming

Every agent gets a `name` that is unique across all seven orchestrators, because
ADK routes by name and they all share one namespace.

- Domain orchestrators: `<domain>_orchestrator` (e.g. `analysis_orchestrator`)
- Specialists: `<domain>_<capability>` (e.g. `analysis_pipeline_health`,
  `events_account_brief`, `mops_list_load`)

The prefix is not decoration. `content_brief` and `analysis_campaign_brief`
would be genuinely ambiguous to the router without it.

## 3. Descriptions are routing logic

The root LLM picks a sub-agent by reading its `description`. That string is the
only thing standing between a user request and the right specialist, so treat it
as code:

- Say what the agent **does** and what it is **for**, in one or two sentences.
- Include the words a user would actually say. If people ask for "the demand gen
  deck", that phrase belongs in the description.
- **Say what it is not for** when there is a near neighbour on the other person's
  side. This is the single highest-value habit in a seven-orchestrator system.

Good:

```python
description=(
    "Analyses how existing marketing campaigns performed: spend, leads, "
    "conversion rates, cost per opportunity and week-over-week trends. "
    "Use for questions about results of campaigns that already ran. "
    "NOT for designing or writing a new campaign."
)
```

Bad: `description="Campaign agent"`

Any change to a description means re-running `evals/routing.evalset.json`.

## 4. Session state key prefixes

All seven orchestrators share one session state dictionary, so every key is
namespaced by its owning domain. Reading another domain's key is allowed;
writing one is not.

| Prefix      | Owner              |
| ----------- | ------------------ |
| `analysis_` | Analysis           |
| `events_`   | Regional Events    |
| `mops_`     | Marketing Ops      |
| `campaign_` | Campaign Design    |
| `abm_`      | ABM                |
| `content_`  | Content Generation |
| `brand_`    | Brand              |

Set them with `output_key="analysis_pipeline_health"` and read them in an
instruction with `{analysis_pipeline_health}`, or `{analysis_pipeline_health?}`
to allow it to be missing.

**Underscores, not dots.** This looks like a style choice and is not. ADK only
substitutes a template variable if the key is a valid Python identifier, so
`{analysis.pipeline_health}` is left in the prompt as literal text. The agent
then reads the words "analysis.pipeline_health" instead of the data, and
nothing errors. Keep every state key a valid identifier.

## 5. Coordinate tasks, share calculations

If your agent needs a number another domain also uses, import the function from
`packages/mktg_core/metrics/`. Do not invoke another orchestrator just to get a
calculation. Every invocation is another LLM call, more latency, and another
chance for the answer to drift.

The root coordinator invokes domain orchestrators as `AgentTool`s. A completed
tool call returns control to root, so root can execute every part of a
multi-domain request in dependency order and every new user turn begins at
root. Domain orchestrators should complete only their assigned scope and return
grounded results; they must not fill in work owned by another domain.

Cross-domain invocation is for handing over a **task**. Importing is for getting
a **calculation**.

---

## Two rules that apply to agent behaviour

**Never let the model do arithmetic.** Every number comes from
`mktg_core.metrics` as a finished table; the agent explains it. A model that
computes pipeline coverage will produce a fluent, confident, wrong answer, and
the first thing a stakeholder checks in a demo is a number they already know.

**Decks are data, not files.** An agent emits a `DeckSpec` as JSON and
`mktg_core.rendering` turns it into a `.pptx`. No agent generates a binary.
