"""Task menu, filter catalogs, and prompt composition for the marketing workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

from mktg_core.connectors import get_connectors
from mktg_core.connectors._fixtures import load
from mktg_core.profile import current_user
from mktg_core.rendering.artifact import OUTPUT_DIR

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_EMPTY_TAIL = re.compile(
    r"\s+(?:for|using|around|related to|at|in|from|on|covering|as a|as an)\s*(?=[.,:;?!]|$)",
    re.I,
)
_EMPTY_FOR_AS = re.compile(r"\s+for\s+(?=as\b)", re.I)
_EMPTY_PARENS = re.compile(r"\s*\(\s*\)")
_BROKEN_ASK = re.compile(r"\bhow did perform\b|\bimprove  performance\b", re.I)

TASK_MENU: tuple[dict, ...] = (
    {
        "id": "campaign_design",
        "label": "Campaign Design",
        "items": (
            {
                "id": "campaign_ideation",
                "label": "Campaign ideation",
                "default_prompt": (
                    "Suggest 3-5 campaign ideas scored on pipeline gaps and "
                    "performance. Lead with one recommendation."
                ),
                "scoped_prompt": (
                    "Suggest 3-5 {campaign_type} campaign ideas scored on pipeline "
                    "gaps and performance. Lead with one recommendation."
                ),
            },
            {
                "id": "campaign_brief",
                "label": "Build me a campaign brief",
                "default_prompt": (
                    "Build a full campaign brief: goal, audience, messages, "
                    "channels, budget, timeline, and KPIs."
                ),
                "scoped_prompt": (
                    "Build a full campaign brief for {campaign} as a {campaign_type}: "
                    "goal, audience, messages, channels, budget, timeline, and KPIs."
                ),
            },
            {
                "id": "campaign_ppt",
                "label": "Generate a campaign PowerPoint",
                "default_prompt": (
                    "Generate a PPT for the upcoming selected campaign."
                ),
                "scoped_prompt": (
                    "Generate a PPT for {campaign}."
                ),
            },
            {
                "id": "competitive_messaging",
                "label": "Build competitive messaging",
                "default_prompt": (
                    "Build competitive messaging: battlecards, objection handlers, "
                    "and displacement lines."
                ),
                "scoped_prompt": (
                    "Build competitive messaging for {campaign_type} using {content}."
                ),
            },
        ),
    },
    {
        "id": "abm",
        "label": "ABM",
        "items": (
            {
                "id": "abm_account_selection",
                "label": "Prioritize accounts",
                "default_prompt": (
                    "Rank target accounts for ABM this quarter and tell me who to prioritize."
                ),
                "scoped_prompt": (
                    "Rank target accounts around {campaign} and tell me who to prioritize."
                ),
            },
            {
                "id": "abm_account_intel",
                "label": "Brief this account",
                "default_prompt": (
                    "Write an intel brief for a named account: intent, buying "
                    "committee, open pipeline, and the next play."
                ),
                "scoped_prompt": (
                    "Write an intel brief for {account}: intent, buying committee, "
                    "open pipeline, and the next play."
                ),
            },
            {
                "id": "abm_gap_value",
                "label": "Map gaps and value",
                "default_prompt": (
                    "Map gaps and quantified value for a named account."
                ),
                "scoped_prompt": "Map gaps and quantified value for {account}.",
            },
            {
                "id": "abm_messaging",
                "label": "Write persona messaging",
                "default_prompt": (
                    "Write persona messaging for the buying committee at a named account."
                ),
                "scoped_prompt": "Write persona messaging for the buying committee at {account}.",
            },
            {
                "id": "abm_multichannel",
                "label": "Build the multi-channel play",
                "default_prompt": (
                    "Build a multi-channel ABM play for a named account: "
                    "email, LinkedIn, Folloze, and a sales playbook."
                ),
                "scoped_prompt": (
                    "Build a multi-channel ABM play for {account}: "
                    "email, LinkedIn, Folloze, and a sales playbook."
                ),
            },
        ),
    },
    {
        "id": "content",
        "label": "Content Generation (Jasper)",
        "items": (
            {
                "id": "write_content",
                "label": "Build anchor asset",
                "default_prompt": "Write an anchor asset grounded in the selected campaign.",
                "scoped_prompt": "Write an anchor asset for {campaign} as a {asset_type}.",
            },
            {
                "id": "translate_asset",
                "label": "Translate asset",
                "default_prompt": "Translate the selected marketing asset for a regional campaign.",
                "scoped_prompt": "Translate {content} for a regional campaign.",
            },
            {
                "id": "asset_grid",
                "label": "Build an asset grid",
                "section": "Asset grid",
                "default_prompt": (
                    "Build an asset grid for product launch, global campaign, "
                    "regional campaign, industry, and competitive plays."
                ),
                "scoped_prompt": "Build an asset grid around {campaign} using {content}.",
            },
            {
                "id": "asset_grid_product_launch",
                "label": "Product launch",
                "section": "Asset grid",
                "default_prompt": "Build an asset grid for a product launch.",
                "scoped_prompt": "Build a product-launch asset grid for {campaign} using {content}.",
            },
            {
                "id": "asset_grid_global",
                "label": "Global campaign",
                "section": "Asset grid",
                "default_prompt": "Build an asset grid for a global campaign.",
                "scoped_prompt": "Build a global-campaign asset grid for {campaign} using {content}.",
            },
            {
                "id": "asset_grid_regional",
                "label": "Regional campaign",
                "section": "Asset grid",
                "default_prompt": "Build an asset grid for a regional campaign.",
                "scoped_prompt": "Build a regional-campaign asset grid for {campaign} using {content}.",
            },
            {
                "id": "asset_grid_industry",
                "label": "Industry",
                "section": "Asset grid",
                "default_prompt": "Build an industry asset grid.",
                "scoped_prompt": "Build an industry asset grid for {campaign} using {content}.",
            },
            {
                "id": "asset_grid_competitive",
                "label": "Competitive",
                "section": "Asset grid",
                "default_prompt": "Build a competitive asset grid.",
                "scoped_prompt": "Build a competitive asset grid for {campaign} using {content}.",
            },
        ),
    },
    {
        "id": "brand",
        "label": "Brand",
        "items": (
            {
                "id": "sentiment",
                "label": "Social media sentiment monitor and response writer",
                "default_prompt": "What is social sentiment doing this week, and do we need a response?",
                "scoped_prompt": "What is social sentiment doing for {campaign}, and do we need a response?",
            },
            {
                "id": "share_of_voice",
                "label": "Share of voice monitor",
                "default_prompt": "Assess our current share of voice and the main competitive movements.",
                "scoped_prompt": "Assess share of voice for {campaign}.",
            },
            {
                "id": "news_sentiment",
                "label": "New topic analysis and sentiment monitor",
                "default_prompt": "Monitor relevant news topics and summarise current sentiment.",
                "scoped_prompt": "Monitor news topics and sentiment related to {campaign}.",
            },
            {
                "id": "rapid_response",
                "label": "Rapid response campaign builder",
                "default_prompt": "Build a rapid response campaign for the current brand issue.",
                "scoped_prompt": "Build a rapid response campaign related to {campaign}.",
            },
        ),
    },
    {
        "id": "analysis",
        "label": "Analysis",
        "items": (
            {
                "id": "campaign_performance",
                "label": "Campaign performance analysis",
                "default_prompt": "How did our campaigns perform this quarter? Call out spend, MQLs and cost per opportunity.",
                "scoped_prompt": (
                    "How did {campaign} perform in {region}? Call out spend, MQLs "
                    "and cost per opportunity."
                ),
                "geo_prompt": (
                    "How did {region} campaigns perform this quarter? Call out spend, "
                    "MQLs, cost per opportunity, and the gap to pipeline target."
                ),
            },
            {
                "id": "budget_shift",
                "label": "Build suggestions to improve campaign performance",
                "default_prompt": "Build suggestions to improve campaign performance. Call out where to move budget and which plays to scale.",
                "scoped_prompt": (
                    "Build suggestions to improve {campaign} performance in {region}."
                ),
                "geo_prompt": (
                    "Build suggestions to improve {region} campaign performance. "
                    "Call out where to move budget to close the pipeline gap."
                ),
            },
        ),
    },
    {
        "id": "events",
        "label": "Regional Event Marketing",
        "items": (
            {
                "id": "event_location",
                "label": "Analyse accounts with no opportunity and suggest event locations and topics",
                "default_prompt": (
                    "Analyse accounts with no opportunity and tell me where we should "
                    "run our next field event, and what the session should be about."
                ),
                "scoped_prompt": (
                    "Analyse accounts with no opportunity around {event} and tell me where "
                    "we should run our next field event, and what the session should be about."
                ),
            },
            {
                "id": "attendee_list",
                "label": "Build a list of targeted contacts in account for event",
                "default_prompt": (
                    "Who should we invite to the next field event from the selected campaigns?"
                ),
                "scoped_prompt": "Who should we invite to {event} from the selected campaigns?",
            },
            {
                "id": "account_briefs",
                "label": "Provide a brief on each account attending an event",
                "default_prompt": "Write account briefs for reps attending the next field event.",
                "scoped_prompt": "Write account briefs for reps attending {event}.",
            },
            {
                "id": "pipeline_in_room",
                "label": "Summarise pipeline in the room for this event",
                "default_prompt": "Summarise the pipeline in the room for the next field event.",
                "scoped_prompt": "Summarise the pipeline in the room for {event}.",
            },
        ),
    },
    {
        "id": "mops",
        "label": "Marketing Operations",
        "items": (
            {
                "id": "create_campaign",
                "label": "SFDC campaign creator",
                "default_prompt": (
                    "Create a Salesforce campaign from the selected type and campaigns."
                ),
                "scoped_prompt": (
                    "Create a {campaign_type} campaign in Salesforce for {campaign}."
                ),
            },
            {
                "id": "sixsense_segment",
                "label": "Build me a segment in 6sense",
                "default_prompt": (
                    "Build a 6sense segment from the selected campaigns and accounts. "
                    "Echo the filters and match count; do not invent accounts."
                ),
                "scoped_prompt": (
                    "Build a 6sense segment using the selected campaigns around {campaign}. "
                    "Echo the filters and match count; do not invent accounts."
                ),
            },
            {
                "id": "marketo_deploy",
                "label": "Deploy segment to Marketo",
                "default_prompt": "Deploy the latest 6sense segment into Marketo.",
                "scoped_prompt": "Deploy the 6sense segment for {campaign} into Marketo.",
            },
            {
                "id": "list_load",
                "label": "List load into Marketo",
                "default_prompt": "Load the selected event's lead list into Marketo.",
                "scoped_prompt": "Load the lead list for {event} into Marketo.",
            },
        ),
    },
)

GROUP_AGENT = {
    "analysis": "analysis_orchestrator",
    "events": "events_orchestrator",
    "mops": "mops_orchestrator",
    "campaign_design": "campaign_design_orchestrator",
    "abm": "abm_orchestrator",
    "content": "content_orchestrator",
    "brand": "brand_orchestrator",
}

# After a briefing, offer the next job in the same scope. Keys are task ids.
TASK_NEXT = {
    "campaign_ideation": "campaign_brief",
    "campaign_brief": "campaign_ppt",
    "campaign_ppt": "write_content",
    "competitive_messaging": "write_content",
    "write_content": "asset_grid",
    "translate_asset": "asset_grid",
    "asset_grid": "create_campaign",
    "asset_grid_product_launch": "create_campaign",
    "asset_grid_global": "create_campaign",
    "asset_grid_regional": "create_campaign",
    "asset_grid_industry": "create_campaign",
    "asset_grid_competitive": "create_campaign",
    "campaign_variant": "create_campaign",
    "create_campaign": "sixsense_segment",
    "sixsense_segment": "marketo_deploy",
    "marketo_deploy": "campaign_performance",
    "list_load": "campaign_performance",
    "event_location": "attendee_list",
    "attendee_list": "account_briefs",
    "account_briefs": "pipeline_in_room",
    "pipeline_in_room": "list_load",
    "campaign_performance": "budget_shift",
    "budget_shift": "sixsense_segment",
    "abm_account_selection": "abm_account_intel",
    "abm_account_intel": "abm_gap_value",
    "abm_gap_value": "abm_messaging",
    "abm_messaging": "abm_multichannel",
    "sentiment": "rapid_response",
    "share_of_voice": "competitive_messaging",
    "news_sentiment": "rapid_response",
    "rapid_response": "campaign_brief",
}

# The task controls which right-rail dimensions are meaningful. Keeping this
# policy outside the prompts makes it testable and lets the browser disable
# irrelevant categories before a request is sent.
TASK_FILTER_POLICY: dict[str, dict[str, list[str]]] = {
    "campaign_performance": {
        "categories": ["campaigns", "campaign_types"],
    },
    "budget_shift": {
        "categories": ["campaigns", "campaign_types"],
    },
    "pipeline_health": {
        "categories": ["campaigns", "campaign_types"],
    },
    "asset_influence": {
        "categories": ["asset_types", "content"],
    },
    "pipeline_deck": {
        "categories": ["campaigns", "campaign_types"],
    },
    "demand_council_deck": {
        "categories": ["campaigns", "campaign_types"],
    },
    "event_location": {
        "categories": ["campaign_types", "events"],
        "campaign_types": ["Field Event", "Tradeshow"],
    },
    "attendee_list": {
        "categories": ["campaigns", "campaign_types", "events"],
        "campaign_types": ["Field Event", "Tradeshow"],
    },
    "account_briefs": {
        "categories": ["campaigns", "campaign_types", "events"],
        "campaign_types": ["Field Event", "Tradeshow"],
    },
    "pipeline_in_room": {
        "categories": ["campaigns", "campaign_types", "events"],
        "campaign_types": ["Field Event", "Tradeshow"],
    },
    "create_campaign": {
        "categories": ["campaigns", "campaign_types", "accounts"],
    },
    "sixsense_segment": {
        "categories": ["campaigns", "accounts"],
    },
    "marketo_deploy": {
        "categories": ["campaigns", "campaign_types"],
    },
    "list_load": {
        "categories": ["events"],
    },
    "campaign_ideation": {
        "categories": ["campaign_types", "asset_types"],
    },
    "campaign_brief": {
        "categories": [
            "campaigns",
            "campaign_types",
            "asset_types",
            "content",
        ],
    },
    "campaign_ppt": {
        "categories": [
            "campaigns",
            "campaign_types",
            "asset_types",
            "content",
        ],
    },
    "competitive_messaging": {
        "categories": ["campaign_types", "asset_types", "content"],
    },
    "abm_account_selection": {
        "categories": ["campaigns", "accounts"],
    },
    "abm_account_intel": {
        "categories": ["accounts"],
    },
    "abm_gap_value": {
        "categories": ["accounts"],
    },
    "abm_messaging": {
        "categories": ["accounts"],
    },
    "abm_multichannel": {
        "categories": ["accounts"],
    },
    "write_content": {
        "categories": ["campaigns", "campaign_types", "asset_types", "accounts"],
    },
    "translate_asset": {
        "categories": ["asset_types", "content"],
    },
    "asset_grid": {
        "categories": [
            "campaigns",
            "campaign_types",
            "asset_types",
            "content",
        ],
    },
    "asset_grid_product_launch": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "asset_grid_global": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "asset_grid_regional": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "asset_grid_industry": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "asset_grid_competitive": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "campaign_variant": {
        "categories": [
            "campaigns",
            "campaign_types",
            "asset_types",
            "content",
        ],
    },
    "sentiment": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "share_of_voice": {
        "categories": ["campaigns", "campaign_types"],
    },
    "news_sentiment": {
        "categories": ["campaigns", "campaign_types", "asset_types", "content"],
    },
    "rapid_response": {
        "categories": [
            "campaigns",
            "campaign_types",
            "asset_types",
            "content",
        ],
    },
}

_FILTER_INPUT_NAMES = {
    "campaigns": "campaign",
    "campaign_types": "campaign_type",
    "asset_types": "asset_type",
    "content": "content",
}


def _task_filter_names(task_id: str) -> list[str]:
    policy = TASK_FILTER_POLICY.get(task_id) or {}
    names = [
        _FILTER_INPUT_NAMES[category]
        for category in policy.get("categories", ())
        if category in _FILTER_INPUT_NAMES
    ]
    return list(dict.fromkeys(names))


_TASKS_BY_ID = {
    item["id"]: item for group in TASK_MENU for item in group["items"]
}

_GENERATED_TYPE_HINTS = (
    ("whitepaper", "Whitepaper"),
    ("brochure", "Brochure"),
    ("case study", "Case Study"),
    ("checklist", "Checklist"),
    ("webinar", "Webinar"),
    ("blog", "Blog"),
    ("demo", "Demo"),
    ("guide", "Whitepaper"),
)


def _generated_content_stem(path: Path) -> str:
    name = path.name
    lowered = name.lower()
    for suffix in (".json.md", ".md"):
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _generated_content_type(text: str) -> str:
    lowered = text.lower()
    for needle, label in _GENERATED_TYPE_HINTS:
        if needle in lowered:
            return label
    return "Whitepaper"


def _generated_content_items() -> list[dict[str, str]]:
    """Named files James wrote under output/content, so they can be ticked later."""
    folder = OUTPUT_DIR / "content"
    if not folder.is_dir():
        return []
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in sorted(folder.glob("*.md")):
        stem = _generated_content_stem(path)
        if not stem or stem in seen:
            continue
        seen.add(stem)
        title = ""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except OSError:
            continue
        label = title or stem.replace("_", " ")
        items.append(
            {
                "id": f"OUT-{stem}",
                "label": label,
                "type": _generated_content_type(f"{stem} {label}"),
            }
        )
    return items

@dataclass
class FilterSelection:
    campaigns: list[str] = field(default_factory=list)
    campaign_types: list[str] = field(default_factory=list)
    asset_types: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    accounts: list[str] = field(default_factory=list)
    geos: list[str] = field(default_factory=list)


def workspace_catalog() -> dict:
    """Return tasks and filters backed by the mock marketing dataset."""
    me = current_user()
    assistant = {
        "name": "James",
        "title": "James",
        "tagline": "See the gap, then ask James to fix, write, or load the list.",
        "region": me.get("region", "EMEA"),
        "owner": me.get("full_name") or me.get("name") or "",
    }
    connectors = get_connectors()
    sfdc = connectors.sfdc
    campaigns = list(sfdc.list_campaigns())
    events = list(connectors.events.list_events())
    target_accounts = [
        account for account in sfdc.list_accounts() if account.is_target_account
    ]
    engagement_events = load("engagement_events.json")
    assets = {
        row["asset_id"]: {
            "id": row["asset_id"],
            "label": row["asset_name"],
            "type": row["asset_type"],
        }
        for row in engagement_events
    }
    for item in _generated_content_items():
        assets.setdefault(item["id"], item)
    campaign_types = sorted({row.type.value for row in campaigns})
    asset_types = sorted({row["type"] for row in assets.values()})
    from ui.dashboard import _health

    tasks = [
        {
            "id": group["id"],
            "label": group["label"],
            "agent": GROUP_AGENT[group["id"]],
            "items": [
                {
                    **dict(item),
                    "filter_policy": TASK_FILTER_POLICY[item["id"]],
                    "filters": _task_filter_names(item["id"]),
                    "next_task": TASK_NEXT.get(item["id"], ""),
                }
                for item in group["items"]
            ],
        }
        for group in TASK_MENU
        if group["id"] in GROUP_AGENT
    ]
    return {
        "assistant": assistant,
        "ui": {"reasoning": True},
        "agents": [
            {"id": group["id"], "label": group["label"], "agent": group["agent"]}
            for group in tasks
        ],
        "tasks": tasks,
        "filters": {
            "geos": [
                {"id": "AMER", "label": "AMER"},
                {"id": "EMEA", "label": "EMEA"},
                {"id": "APJ", "label": "APJ"},
            ],
            "campaigns": [
                {
                    "id": row.id,
                    "label": row.name,
                    "region": row.region.value,
                    "type": row.type.value,
                    "spend": int(row.spend_usd),
                    "start_date": row.start_date.isoformat(),
                    "end_date": row.end_date.isoformat(),
                    "health": _health(
                        int(row.spend_usd),
                        int(row.mqls),
                        int(row.mqls_one_week_ago),
                    ),
                }
                for row in campaigns
            ],
            "campaign_types": [
                {"id": campaign_type, "label": campaign_type}
                for campaign_type in campaign_types
            ],
            "asset_types": [
                {"id": asset_type, "label": asset_type}
                for asset_type in asset_types
            ],
            "content": list(assets.values()),
            "events": [
                {
                    "id": row.id,
                    "label": f"{row.name} ({row.city})",
                    "region": row.region.value,
                    "name": row.name,
                }
                for row in events
            ],
            "accounts": [
                {
                    "id": row.id,
                    "label": row.name,
                    "region": row.region.value,
                }
                for row in target_accounts
            ],
        },
    }


def _campaign_index() -> dict[str, dict[str, str]]:
    catalog = workspace_catalog()
    return {item["id"]: item for item in catalog["filters"]["campaigns"]}


def _event_index() -> dict[str, dict[str, str]]:
    catalog = workspace_catalog()
    return {item["id"]: item for item in catalog["filters"]["events"]}


def _account_index() -> dict[str, dict[str, str]]:
    catalog = workspace_catalog()
    return {item["id"]: item for item in catalog["filters"]["accounts"]}


def _labels_for(selected: list[str], catalog_name: str) -> list[str]:
    catalog = workspace_catalog()["filters"][catalog_name]
    index = {item["id"]: item["label"] for item in catalog}
    return [index[item_id] for item_id in selected if item_id in index]


def _first_label(
    selected: list[str], catalog_name: str, fallback: str = ""
) -> str:
    labels = _labels_for(selected, catalog_name)
    return labels[0] if labels else fallback


def _first_region(selection: FilterSelection) -> str:
    if selection.geos:
        return selection.geos[0]
    campaigns = _campaign_index()
    for campaign_id in selection.campaigns:
        if campaign_id in campaigns:
            return campaigns[campaign_id]["region"]
    accounts = _account_index()
    for account_id in selection.accounts:
        if account_id in accounts:
            return accounts[account_id]["region"]
    events = _event_index()
    for event_id in selection.events:
        if event_id in events:
            return events[event_id]["region"]
    return ""


def _join_names(names: list[str]) -> str:
    labels = [name for name in names if name]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _campaign_name(label: str) -> str:
    return label.split(" · ", 1)[-1]


def _joined_campaigns(selection: FilterSelection) -> str:
    campaigns = _campaign_index()
    return _join_names(
        [
            _campaign_name(campaigns[campaign_id]["label"])
            for campaign_id in selection.campaigns
            if campaign_id in campaigns
        ]
    )


def _joined_campaign_types(selection: FilterSelection) -> str:
    if selection.campaign_types:
        return _join_names(selection.campaign_types)
    campaigns = _campaign_index()
    types: list[str] = []
    for campaign_id in selection.campaigns:
        campaign_type = campaigns.get(campaign_id, {}).get("type") or ""
        if campaign_type and campaign_type not in types:
            types.append(campaign_type)
    return _join_names(types)


def _joined_events(selection: FilterSelection) -> str:
    events = _event_index()
    return _join_names(
        [
            events[event_id]["name"]
            for event_id in selection.events
            if event_id in events
        ]
    )


def _joined_accounts(selection: FilterSelection) -> str:
    accounts = _account_index()
    return _join_names(
        [
            accounts[account_id]["label"]
            for account_id in selection.accounts
            if account_id in accounts
        ]
    )


def _fill_prompt(template: str | None, values: dict[str, str]) -> str | None:
    if not template:
        return None
    needed = _PLACEHOLDER.findall(template)
    if needed and not any(values.get(name) for name in needed):
        return None
    text = _PLACEHOLDER.sub(lambda match: values.get(match.group(1), "") or "", template)
    text = re.sub(r"\s{2,}", " ", text)
    text = _EMPTY_FOR_AS.sub("", text)
    text = _EMPTY_TAIL.sub("", text)
    text = _EMPTY_PARENS.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,:;?!])", r"\1", text).strip()
    if not text or _PLACEHOLDER.search(text) or _BROKEN_ASK.search(text):
        return None
    return text


def _selection_values(selection: FilterSelection) -> dict[str, str]:
    region = ""
    if selection.geos:
        region = _join_names(list(dict.fromkeys(selection.geos)))
    else:
        region = _first_region(selection)
    return {
        "account": _joined_accounts(selection),
        "region": region,
        "territory": region,
        "campaign": _joined_campaigns(selection),
        "campaign_type": _joined_campaign_types(selection),
        "event": _joined_events(selection),
        "content": _join_names(_labels_for(selection.content, "content")),
        "asset_type": _join_names(selection.asset_types),
    }


def _has_filters(selection: FilterSelection) -> bool:
    return any(
        (
            selection.campaigns,
            selection.campaign_types,
            selection.asset_types,
            selection.content,
            selection.events,
            selection.accounts,
            selection.geos,
        )
    )


def compose_task_message(
    task_id: str, selection: FilterSelection | None = None
) -> str:
    """Turn a left-nav task plus right-rail filters into one prompt."""
    task = _TASKS_BY_ID.get(task_id)
    if task is None:
        raise KeyError(task_id)
    selection = selection or FilterSelection()
    values = _selection_values(selection)
    filled = _fill_prompt(task.get("scoped_prompt"), values)
    if filled:
        text = filled
    else:
        geo = _fill_prompt(task.get("geo_prompt"), values)
        text = geo or str(task["default_prompt"])
    facts = write_task_facts(task_id, selection)
    if facts:
        return text + "\n\n" + facts
    return text


def apply_write_facts(
    text: str, task_id: str | None, selection: FilterSelection | None
) -> str:
    if not task_id:
        return text
    facts = write_task_facts(task_id, selection)
    if not facts or facts in (text or ""):
        return text
    return text.rstrip() + "\n\n" + facts


def _quarter_for(value: date) -> str:
    return f"{value.year}Q{(value.month - 1) // 3 + 1}"


def _campaign_slug(name: str, campaign_type: str) -> str:
    text = name.strip()
    prefix = f"{campaign_type} - "
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix) :]
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return slug or "Campaign"


def _parse_iso_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def write_task_facts(task_id: str, selection: FilterSelection | None = None) -> str:
    """Pin the mocked Salesforce write to values taken from the ticked filters."""
    if task_id in _ACCOUNT_TASKS and (selection.accounts if selection else []):
        account_id = selection.accounts[0]
        label = _account_index().get(account_id, {}).get("label") or account_id
        return (
            f"Use account id {account_id} ({label}). "
            f"Call the account tool with {account_id}."
        )
    if task_id != "create_campaign":
        return ""
    selection = selection or FilterSelection()
    campaigns = _campaign_index()
    row = next(
        (campaigns[item] for item in selection.campaigns if item in campaigns),
        None,
    )
    campaign_type = (
        selection.campaign_types[0]
        if selection.campaign_types
        else (row or {}).get("type") or ""
    )
    region = _first_region(selection) or current_user().get("region") or "EMEA"
    start = _parse_iso_date((row or {}).get("start_date") or "")
    end = _parse_iso_date((row or {}).get("end_date") or "")
    if start is None or end is None:
        start = date.today()
        end = start + timedelta(days=90)
    budget = int((row or {}).get("spend") or 25000)
    owner = current_user().get("email") or "owner@gru.com"
    if not campaign_type:
        return ""
    slug = _campaign_slug((row or {}).get("label") or campaign_type, campaign_type)
    name = f"{region}-{campaign_type}-{_quarter_for(start)}-{slug}"
    return (
        "Use exactly these values and call create_sfdc_campaign once:\n"
        f"- Name: {name}\n"
        f"- Type: {campaign_type}\n"
        f"- Region: {region}\n"
        f"- Dates: {start.isoformat()} to {end.isoformat()}\n"
        f"- Budget: {budget} USD\n"
        f"- Owner: {owner}"
    )


def filter_tag_items(selection: FilterSelection) -> list[dict[str, str]]:
    """Labels for composer/history tags, keyed to the checkbox name."""
    names = {
        "campaigns": "campaign",
        "campaign_types": "campaign-type",
        "asset_types": "asset-type",
        "content": "content",
        "events": "event",
        "accounts": "account",
    }
    tags: list[dict[str, str]] = []
    campaigns = _campaign_index()
    for campaign_id in selection.campaigns:
        label = campaigns.get(campaign_id, {}).get("label")
        if label:
            tags.append(
                {
                    "kind": "Campaign",
                    "label": label,
                    "category": "campaigns",
                    "value": campaign_id,
                    "name": names["campaigns"],
                }
            )
    for value in selection.campaign_types:
        tags.append(
            {
                "kind": "Type",
                "label": value,
                "category": "campaign_types",
                "value": value,
                "name": names["campaign_types"],
            }
        )
    for value in selection.asset_types:
        tags.append(
            {
                "kind": "Asset type",
                "label": value,
                "category": "asset_types",
                "value": value,
                "name": names["asset_types"],
            }
        )
    for content_id in selection.content:
        labels = _labels_for([content_id], "content")
        if labels:
            tags.append(
                {
                    "kind": "Content",
                    "label": labels[0],
                    "category": "content",
                    "value": content_id,
                    "name": names["content"],
                }
            )
    events = _event_index()
    for event_id in selection.events:
        label = events.get(event_id, {}).get("label")
        if label:
            tags.append(
                {
                    "kind": "Event",
                    "label": label,
                    "category": "events",
                    "value": event_id,
                    "name": names["events"],
                }
            )
    accounts = _account_index()
    for account_id in selection.accounts:
        label = accounts.get(account_id, {}).get("label")
        if label:
            tags.append(
                {
                    "kind": "Account",
                    "label": label,
                    "category": "accounts",
                    "value": account_id,
                    "name": names["accounts"],
                }
            )
    return tags


def filter_notes(selection: FilterSelection) -> list[str]:
    notes: list[str] = []
    if selection.geos:
        notes.append("Geo: " + ", ".join(selection.geos))
    if selection.campaigns:
        labels = [
            _campaign_index()[campaign_id]["label"]
            for campaign_id in selection.campaigns
            if campaign_id in _campaign_index()
        ]
        if labels:
            notes.append("Campaigns: " + "; ".join(labels))
    if selection.campaign_types:
        notes.append("Campaign types: " + ", ".join(selection.campaign_types))
    if selection.asset_types:
        notes.append("Asset types: " + ", ".join(selection.asset_types))
    if selection.content:
        labels = _labels_for(selection.content, "content")
        if labels:
            notes.append("Content: " + "; ".join(labels))
    if selection.events:
        labels = _labels_for(selection.events, "events")
        if labels:
            notes.append("Events: " + "; ".join(labels))
    if selection.accounts:
        labels = _labels_for(selection.accounts, "accounts")
        if labels:
            notes.append("Accounts: " + "; ".join(labels))
    return notes


def apply_filter_notes(text: str, selection: FilterSelection | None) -> str:
    notes = filter_notes(selection or FilterSelection())
    if not notes:
        return text
    return text + "\n\nWorking filters:\n" + "\n".join(f"- {note}" for note in notes)


_ACCOUNT_TASKS = (
    "abm_account_intel",
    "abm_gap_value",
    "abm_messaging",
    "abm_multichannel",
)
_ACCOUNT_ID_RE = re.compile(r"\bACC-\d+\b", re.I)

WRITE_GUARD_REPLY = (
    "## Question\n"
    "Tick a campaign type and a campaign on the right, then send again.\n"
    "Once those filters are set I will draft the mocked write."
)

_WRITE_FILTER_LABELS = {
    "campaigns": "a campaign",
    "campaign_types": "a campaign type",
    "accounts": "an account",
    "events": "an event",
}


def _selection_values_for(selection: FilterSelection, category: str) -> list[str]:
    return list(getattr(selection, category, []) or [])


def _write_missing_categories(task_id: str, selection: FilterSelection) -> list[str]:
    policy = TASK_FILTER_POLICY.get(task_id) or {}
    categories = list(policy.get("categories") or [])
    if task_id == "create_campaign":
        if selection.campaigns or selection.campaign_types:
            return []
        return ["campaign_types", "campaigns"]
    if task_id == "sixsense_segment":
        if selection.campaigns or selection.accounts:
            return []
        return ["campaigns", "accounts"]
    return [name for name in categories if not _selection_values_for(selection, name)]


def _write_guard_text(missing: list[str], task_id: str = "") -> str:
    labels = [_WRITE_FILTER_LABELS.get(name, name.replace("_", " ")) for name in missing]
    if not labels:
        return WRITE_GUARD_REPLY
    if len(labels) == 1:
        needed = labels[0]
    elif len(labels) == 2:
        needed = f"{labels[0]} and {labels[1]}"
    else:
        needed = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    closer = (
        "Once an account is selected I will write the brief."
        if task_id in _ACCOUNT_TASKS
        else "Once those filters are set I will draft the mocked write."
    )
    return (
        "## Question\n"
        f"Tick {needed} on the right, then send again.\n"
        f"{closer}"
    )


def task_id_from_message(message: str) -> str:
    compact = " ".join((message or "").split())
    if not compact:
        return ""
    for task_id, task in _TASKS_BY_ID.items():
        default = " ".join(str(task["default_prompt"]).split())
        if compact == default:
            return task_id
    return ""


def mentioned_account_ids(text: str) -> list[str]:
    catalog = _account_index()
    found: list[str] = []
    for raw in _ACCOUNT_ID_RE.findall(text or ""):
        key = raw.upper()
        if key in catalog and key not in found:
            found.append(key)
    return found


def is_bare_account_id(text: str) -> bool:
    compact = " ".join((text or "").split())
    return bool(_ACCOUNT_ID_RE.fullmatch(compact))


def merge_mentioned_accounts(
    selection: FilterSelection, text: str
) -> FilterSelection:
    ids = mentioned_account_ids(text)
    if not ids:
        return selection
    accounts = list(dict.fromkeys([*selection.accounts, *ids]))
    return replace(selection, accounts=accounts)


def expand_account_follow_up(
    message: str, task_id: str, selection: FilterSelection
) -> str:
    if not is_bare_account_id(message) or not selection.accounts:
        return message
    if task_id in _TASKS_BY_ID:
        return compose_task_message(task_id, selection)
    account_id = selection.accounts[0]
    return (
        f"Write an intel brief for account id {account_id}: intent, buying "
        "committee, open pipeline, and the next play."
    )


def write_guard_reply(
    message: str, selection: FilterSelection | None = None
) -> str | None:
    """Return a Question when the user sent a write-task's unscoped draft."""
    compact = " ".join((message or "").split())
    if not compact:
        return None
    selection = selection or FilterSelection()
    for task_id in ("create_campaign", "sixsense_segment", *_ACCOUNT_TASKS):
        default = " ".join(str(_TASKS_BY_ID[task_id]["default_prompt"]).split())
        if compact != default:
            continue
        missing = _write_missing_categories(task_id, selection)
        if not missing:
            return None
        return _write_guard_text(missing, task_id)
    return None
