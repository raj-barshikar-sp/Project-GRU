"""Marketing campaign book for the dashboard."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from calendar import monthrange

from mktg_core.connectors import get_connectors
from mktg_core.connectors._fixtures import load
from mktg_core.contracts.crm import AS_OF
from mktg_core.metrics.pipeline import coverage_by_region
from mktg_core.profile import current_user
from ui.catalog import TASK_MENU, TASK_NEXT

# Spend bands a demand-gen manager actually uses.
SPEND_FILTERS = (
    {"id": "smb", "label": "Under $25k", "min": 0, "max": 24_999},
    {"id": "mid", "label": "$25k–$75k", "min": 25_000, "max": 74_999},
    {"id": "enterprise", "label": "$75k+", "min": 75_000, "max": None},
)
TIME_FILTERS = (
    {"id": "this_week", "label": "Ends this week"},
    {"id": "this_month", "label": "Ends this month"},
    {"id": "this_quarter", "label": "Ends this quarter"},
    {"id": "stale", "label": "Ended 30d+ ago"},
)
TYPE_SHORT = {
    "Paid Social": "Paid social",
    "Paid Search": "Paid search",
    "Content Syndication": "Syndication",
    "Field Event": "Field",
    "Email Nurture": "Nurture",
    "Tradeshow": "Tradeshow",
    "Webinar": "Webinar",
}
TYPE_ORDER = (
    "Webinar",
    "Field Event",
    "Paid Search",
    "Paid Social",
    "Content Syndication",
    "Email Nurture",
    "Tradeshow",
)
# Fixture campaigns all ended 4 Oct. Spread the book so time filters and
# "ending this week" are usable for marketers, without rewriting CRM maths.
BOOK_ENDS = {
    "CMP-001": date(2026, 10, 31),
    "CMP-002": date(2026, 9, 18),
    "CMP-003": date(2026, 9, 30),
    "CMP-004": date(2026, 9, 6),
    "CMP-005": date(2026, 9, 5),
    "CMP-006": date(2026, 12, 15),
    "CMP-007": date(2026, 6, 12),
    "CMP-008": date(2026, 9, 4),
    "CMP-009": date(2026, 9, 22),
    "CMP-010": date(2026, 8, 1),
    "CMP-011": date(2026, 9, 25),
    "CMP-012": date(2026, 11, 5),
}
SLACK_CHANNELS = {
    "LinkedIn": "#social-listening",
    "X": "#social-listening",
    "Reddit": "#demand-gen",
    "YouTube": "#content",
}
IMPACT = {
    "pipeline_risk": {"label": "Ends soon", "tone": "risk"},
    "budget_waste": {"label": "Move budget", "tone": "risk"},
    "scale_winner": {"label": "Scale this", "tone": "scale"},
    "coverage_gap": {"label": "Behind target", "tone": "watch"},
    "event_fill": {"label": "Fill seats", "tone": "watch"},
    "event_venue": {"label": "Pick city", "tone": "watch"},
    "pick_accounts": {"label": "Pick accounts", "tone": "watch"},
    "build_audience": {"label": "Build audience", "tone": "watch"},
}


def _spend_band_id(amount: int) -> str:
    for bucket in SPEND_FILTERS:
        ceiling = bucket["max"]
        if amount >= int(bucket["min"]) and (ceiling is None or amount <= int(ceiling)):
            return str(bucket["id"])
    return "enterprise"


def _money_short(amount: int) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${round(amount / 1_000)}k"
    return f"${amount:,}"


def _quarter(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3 + 1


def _in_time_window(row: dict[str, Any], window: str, today: date) -> bool:
    close = date.fromisoformat(str(row["end_date"])[:10])
    if window == "this_week":
        start = today - timedelta(days=today.weekday())
        return start <= close < start + timedelta(days=7)
    if window == "this_month":
        return close.year == today.year and close.month == today.month
    if window == "this_quarter":
        return _quarter(close) == _quarter(today)
    if window == "stale":
        return (today - close).days >= 30
    return True


def _health(spend: int, mqls: int, mqls_week_ago: int) -> int:
    if mqls <= 0:
        return 32
    cost = spend / mqls
    trend = mqls - mqls_week_ago
    score = 88 - min(50, int(cost / 40)) + min(12, trend)
    return max(18, min(96, score))


def _theme(name: str) -> str:
    if " - " in name:
        return name.split(" - ", 1)[1]
    return name


def _campaign_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for campaign in get_connectors().sfdc.list_campaigns():
        amount = int(campaign.spend_usd)
        close = BOOK_ENDS.get(campaign.id, campaign.end_date)
        rows.append(
            {
                "id": campaign.id,
                "name": campaign.name,
                "theme": _theme(campaign.name),
                "type": campaign.type.value,
                "spend": amount,
                "spend_band": _spend_band_id(amount),
                "geo": campaign.region.value,
                "end_date": close.isoformat(),
                "health": _health(amount, int(campaign.mqls), int(campaign.mqls_one_week_ago)),
                "mqls": int(campaign.mqls),
                "opps_created": int(campaign.opps_created),
                "leads": int(campaign.leads),
                "backup": amount >= 75_000 and int(campaign.opps_created) <= 2,
            }
        )
    return rows


def _type_filters(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen = {row["type"] for row in rows}
    ordered = [item for item in TYPE_ORDER if item in seen]
    ordered.extend(sorted(seen - set(ordered)))
    return [
        {"id": item, "label": TYPE_SHORT.get(item, item)}
        for item in ordered
    ]


def _quarter_end(day: date) -> date:
    last_month = ((day.month - 1) // 3 + 1) * 3
    return date(day.year, last_month, monthrange(day.year, last_month)[1])


def _coverage_row(geos: list[str]) -> dict[str, Any]:
    table = coverage_by_region(get_connectors())
    if len(geos) == 1:
        key = geos[0]
    else:
        key = "TOTAL"
    for row in table.rows:
        if row["Region"] == key:
            return row
    return table.rows[-1]


def _job_index() -> dict[str, tuple[str, str]]:
    return {
        task["id"]: (group["label"], task["label"])
        for group in TASK_MENU
        for task in group["items"]
    }


def _money(amount: int) -> str:
    value = int(amount or 0)
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${round(value / 1_000)}k"
    return f"${value:,}"


def _cost_per_mql(row: dict[str, Any]) -> int:
    mqls = int(row.get("mqls") or 0)
    spend = int(row.get("spend") or 0)
    if mqls <= 0:
        return spend
    return round(spend / mqls)


def _book_cpmql(rows: list[dict[str, Any]]) -> int:
    spend = sum(int(row.get("spend") or 0) for row in rows)
    mqls = sum(int(row.get("mqls") or 0) for row in rows)
    if mqls <= 0:
        return spend
    return round(spend / mqls)


def _days_to_end(row: dict[str, Any], today: date) -> int:
    close = date.fromisoformat(str(row["end_date"])[:10])
    return (close - today).days


def _end_label(row: dict[str, Any], today: date) -> str:
    close = date.fromisoformat(str(row["end_date"])[:10])
    stamp = close.strftime("%-d %b")
    days = (close - today).days
    if days >= 0:
        return f"ends {stamp} ({days} days)"
    return f"ended {stamp} ({abs(days)} days ago)"


def _detail(row: dict[str, Any], today: date) -> str:
    return (
        f"{row['id']} · {row['geo']} · {row['type']} · "
        f"{_money(int(row['spend']))} spend · {row['mqls']} MQLs · "
        f"${_cost_per_mql(row):,}/MQL · {_end_label(row, today)}"
    )


def _book_detail(rows: list[dict[str, Any]], geos: list[str]) -> str:
    spend = sum(int(row.get("spend") or 0) for row in rows)
    mqls = sum(int(row.get("mqls") or 0) for row in rows)
    geo = geos[0] if len(geos) == 1 else "all geos"
    return f"{len(rows)} campaigns · {geo} · {_money(spend)} spend · {mqls} MQLs"


def _impact_for(task_id: str, row: dict[str, Any] | None = None) -> dict[str, str]:
    if task_id == "budget_shift":
        return IMPACT["budget_waste"]
    if task_id == "attendee_list":
        return IMPACT["event_fill"]
    if task_id == "event_location":
        return IMPACT["event_venue"]
    if task_id in {"write_content", "campaign_brief"}:
        return IMPACT["scale_winner"]
    if task_id == "abm_account_selection":
        return IMPACT["pick_accounts"]
    if task_id == "sixsense_segment":
        return IMPACT["build_audience"]
    if row and row.get("backup"):
        return IMPACT["budget_waste"]
    return IMPACT["pipeline_risk"]


def _prompt(
    task_id: str,
    row: dict[str, Any] | None = None,
    *,
    rows: list[dict[str, Any]] | None = None,
    today: date | None = None,
    coverage: dict[str, Any] | None = None,
    geos: list[str] | None = None,
) -> str:
    book = rows or []
    day = today or AS_OF
    avg = _book_cpmql(book) if book else 0
    geo = geos[0] if geos and len(geos) == 1 else (row["geo"] if row else "this book")
    if row:
        name = str(row["name"])
        cid = str(row["id"])
        spend = _money(int(row["spend"]))
        mqls = int(row["mqls"])
        opps = int(row["opps_created"])
        cpm = _cost_per_mql(row)
        clock = _end_label(row, day)
        facts = (
            f"{name} ({cid}, {row['geo']}) is a {row['type']} play with "
            f"{spend} spend, {mqls} MQLs, {opps} opps, ${cpm:,} per MQL, "
            f"and {clock}."
        )
        if task_id == "campaign_performance":
            return (
                f"{facts} Book average is ${avg:,} per MQL. "
                "Tell me what is working, what is lagging, and the follow-up "
                "play we should lock this week so MQLs and opps do not drop "
                "when the flight ends. Show spend, MQLs, cost per opportunity, "
                "and the gap this campaign leaves if we do nothing."
            )
        if task_id == "budget_shift":
            return (
                f"{facts} Book average is ${avg:,} per MQL. "
                "Tell me how much budget to pull, which campaign to move it "
                "into, and what pipeline that shift buys this quarter. "
                "Show the before/after MQL and cost-per-opp maths."
            )
        if task_id == "write_content":
            return (
                f"{facts} This is the leading MQL engine in the current view. "
                "Write an anchor asset that extends the theme, name the "
                "persona, and say how the asset should be used in paid, "
                "nurture, and sales follow-up so we scale MQLs without a "
                "new spend line."
            )
        if task_id == "campaign_brief":
            return (
                f"{facts} Build a campaign brief for a variant that keeps "
                "this MQL run-rate. Include audience, offer, channels, "
                "success metrics, and the budget needed so demand gen can "
                "brief creative and media this week."
            )
        if task_id == "attendee_list":
            return (
                f"{facts} Build a targeted invite list for this field "
                "program: named accounts with no open opp, the right "
                "contacts, and why each seat matters for pipeline in the "
                "room. Call out who field marketing should chase first."
            )
        if task_id == "event_location":
            return (
                f"{facts} Analyse accounts with no opportunity around this "
                "program and tell me where we should run the next field "
                "event, what the session should be about, and how that "
                "fills coverage in {row['geo']}."
            )
        if task_id == "sixsense_segment":
            return (
                f"{facts} Build a 6sense segment that captures lookalikes "
                "of the accounts this campaign is converting, so we can "
                "feed Marketo and protect pipeline after {clock}."
            )
    spend = sum(int(item.get("spend") or 0) for item in book)
    mqls = sum(int(item.get("mqls") or 0) for item in book)
    book_line = (
        f"This view has {len(book)} campaigns in {geo} with "
        f"{_money(spend)} spend and {mqls} MQLs (book ${avg:,}/MQL)."
    )
    if task_id == "abm_account_selection":
        return (
            f"{book_line} Rank target accounts for ABM this quarter: who "
            "to prioritize, why they close the coverage gap, and what "
            "demand gen should put in front of each buying committee."
        )
    if task_id == "sixsense_segment":
        return (
            f"{book_line} Build a 6sense segment from the campaigns in "
            "view so we can retarget in-market accounts and protect "
            "pipeline this quarter."
        )
    if task_id == "campaign_performance" and coverage:
        gap = int(coverage.get("Gap to target (USD)") or 0)
        days_left = max(0, (_quarter_end(day) - day).days)
        cov = coverage.get("Coverage", "")
        return (
            f"{book_line} Coverage is {cov} with {_money(gap)} still to "
            f"close and {days_left} days left this quarter. How did "
            f"{geo} campaigns perform? Call out spend, MQLs, cost per "
            "opportunity, and the plays that close the gap."
        )
    if task_id == "budget_shift" and coverage:
        gap = int(coverage.get("Gap to target (USD)") or 0)
        return (
            f"{book_line} Gap to target is {_money(gap)}. Build "
            "suggestions to improve campaign performance. Call out where "
            "to move budget to close the pipeline gap this quarter."
        )
    return book_line + " What should marketing do next?"


def _job(
    task_id: str,
    due: str,
    row: dict[str, Any] | None = None,
    *,
    event: str = "",
    account: str = "",
    detail: str = "",
    impact: str = "",
    tone: str = "",
    prompt: str = "",
    title: str = "",
    geo: str = "",
) -> dict[str, str] | None:
    by_id = _job_index()
    if task_id not in by_id:
        return None
    scope, label = by_id[task_id]
    payload = {
        "id": task_id,
        "label": label,
        "scope": scope,
        "due": due,
        "task": task_id,
        "next_task": TASK_NEXT.get(task_id, ""),
    }
    if row:
        payload["campaign"] = str(row["id"])
        payload["geo"] = str(row["geo"])
        payload["type"] = str(row["type"])
    if geo:
        payload["geo"] = geo
    if event:
        payload["event"] = event
    if account:
        payload["account"] = account
    if detail:
        payload["detail"] = detail
    if impact:
        payload["impact"] = impact
        payload["tone"] = tone or "watch"
    if prompt:
        payload["prompt"] = prompt
    if title:
        payload["title"] = title
    return payload


def _task_bar(
    rows: list[dict[str, Any]],
    today: date,
    *,
    geos: list[str],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(task_id: str, due: str, row: dict[str, Any] | None = None) -> None:
        if task_id in seen:
            return
        badge = _impact_for(task_id, row)
        detail = _detail(row, today) if row else _book_detail(rows, geos)
        job = _job(
            task_id,
            due,
            row,
            detail=detail,
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt(task_id, row, rows=rows, today=today, geos=geos),
            geo=geos[0] if len(geos) == 1 else "",
        )
        if job is None:
            return
        seen.add(task_id)
        items.append(job)

    wrapping = [row for row in rows if _in_time_window(row, "this_week", today)]
    pits = [row for row in rows if row["backup"]]
    field = [row for row in rows if row["type"] in {"Field Event", "Tradeshow"}]
    winners = sorted(rows, key=lambda item: item["mqls"], reverse=True)
    if wrapping:
        add("campaign_performance", "Today", wrapping[0])
    if pits:
        add("budget_shift", "Today", pits[0])
    if field:
        add("attendee_list", "This week", field[0])
    add("abm_account_selection", "This week")
    if rows and "campaign_performance" not in seen:
        add("campaign_performance", "Today", rows[0])
    if winners:
        add("write_content", "Tomorrow", winners[0])
        add("campaign_brief", "Tomorrow", winners[0])
    if field:
        add("event_location", "This week", field[0])
    add("sixsense_segment", "This week", winners[0] if winners else None)
    return items[:6]


def _alerts(
    rows: list[dict[str, Any]],
    today: date,
    *,
    coverage: dict[str, Any],
    geos: list[str],
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []
    wrapping = [row for row in rows if _in_time_window(row, "this_week", today)]
    for row in wrapping[:2]:
        days = _days_to_end(row, today)
        cpm = _cost_per_mql(row)
        badge = IMPACT["pipeline_risk"]
        job = _job(
            "campaign_performance",
            "This week",
            row,
            detail=_detail(row, today),
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt(
                "campaign_performance", row, rows=rows, today=today, geos=geos
            ),
            title=(
                f"{row['theme']} ({row['geo']}) ends in {days} days at "
                f"${cpm:,}/MQL. Lock the follow-up so MQLs do not fall off."
            ),
        )
        if job:
            notes.append(job)
    pits = [row for row in rows if row["backup"]]
    for row in pits[:2]:
        badge = IMPACT["budget_waste"]
        job = _job(
            "budget_shift",
            "Budget",
            row,
            detail=_detail(row, today),
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt("budget_shift", row, rows=rows, today=today, geos=geos),
            title=(
                f"{row['name']} is {_money(int(row['spend']))} for "
                f"{row['opps_created']} opps (${_cost_per_mql(row):,}/MQL). "
                "Move spend before the quarter closes."
            ),
        )
        if job:
            notes.append(job)
    winners = sorted(rows, key=lambda item: item["mqls"], reverse=True)
    if winners:
        top = winners[0]
        badge = IMPACT["scale_winner"]
        job = _job(
            "write_content",
            "Scale",
            top,
            detail=_detail(top, today),
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt("write_content", top, rows=rows, today=today, geos=geos),
            title=(
                f"{top['theme']} is leading with {top['mqls']} MQLs at "
                f"${_cost_per_mql(top):,}/MQL. Brief a variant to scale it."
            ),
        )
        if job:
            notes.append(job)
    gap = int(coverage.get("Gap to target (USD)") or 0)
    if gap > 0:
        badge = IMPACT["coverage_gap"]
        days_left = max(0, (_quarter_end(today) - today).days)
        geo = geos[0] if len(geos) == 1 else "the book"
        job = _job(
            "campaign_performance",
            "Quarter",
            detail=_book_detail(rows, geos),
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt(
                "campaign_performance",
                rows=rows,
                today=today,
                coverage=coverage,
                geos=geos,
            ),
            geo=geos[0] if len(geos) == 1 else "",
            title=(
                f"{geo} is {_money(gap)} short of target with {days_left} "
                "days left. Coverage will miss if mix stays put."
            ),
        )
        if job:
            notes.append(job)
    stale = [row for row in rows if _in_time_window(row, "stale", today)]
    if stale:
        row = stale[0]
        badge = IMPACT["pipeline_risk"]
        job = _job(
            "campaign_performance",
            "Stale",
            row,
            detail=_detail(row, today),
            impact=badge["label"],
            tone=badge["tone"],
            prompt=_prompt(
                "campaign_performance", row, rows=rows, today=today, geos=geos
            ),
            title=(
                f"{row['name']} {_end_label(row, today)} and still sits in "
                "the book. Decide whether to recycle budget or close it out."
            ),
        )
        if job:
            notes.append(job)
    return notes[:6]


def _mention_when(raw: str) -> str:
    try:
        return date.fromisoformat(str(raw)[:10]).strftime("%-d %b")
    except ValueError:
        return str(raw)


def _slack_person(author: str) -> tuple[str, str]:
    handle = str(author or "teammate").strip()
    if handle.startswith("@"):
        handle = handle[1:]
    if handle.lower().startswith("u/"):
        handle = handle[2:]
    words = [
        part
        for part in handle.replace(".", " ").replace("_", " ").replace("-", " ").split()
        if part
    ]
    name = " ".join(word.capitalize() for word in words) or "Teammate"
    initials = "".join(word[0] for word in words[:2]).upper() or "?"
    return name, initials


def _slack_time(raw: str, seed: str) -> str:
    minutes = 9 * 60 + (sum(ord(c) for c in seed) % (8 * 60))
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    clock = f"{hour12}:{minute:02d} {suffix}"
    day = _mention_when(raw)
    if not day:
        return clock
    return f"{day} at {clock}"


def _slack() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for mention in load("social_mentions.json")[:5]:
        platform = str(mention.get("platform") or "")
        raw_author = str(mention.get("author") or "")
        name, initials = _slack_person(raw_author)
        seed = str(mention.get("id") or raw_author)
        items.append(
            {
                "channel": SLACK_CHANNELS.get(platform, "#marketing"),
                "author": name,
                "initials": initials,
                "when": _slack_time(str(mention.get("date") or ""), seed),
                "text": str(mention.get("text") or ""),
            }
        )
    return items


def _row_in_view(
    row: dict[str, Any],
    *,
    geos: list[str],
    spend: list[str],
    types: list[str],
    windows: list[str],
    today: date,
    skip: str = "",
) -> bool:
    if skip != "geo" and geos and row["geo"] not in geos:
        return False
    if skip != "spend" and spend and row["spend_band"] not in spend:
        return False
    if skip != "type" and types and row["type"] not in types:
        return False
    if skip != "window" and windows and not any(
        _in_time_window(row, window, today) for window in windows
    ):
        return False
    return True


def dashboard_payload(
    *,
    geos: list[str] | None = None,
    spend: list[str] | None = None,
    types: list[str] | None = None,
    windows: list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or AS_OF
    geos = [item for item in (geos or []) if item]
    spend_bands = [item for item in (spend or []) if item]
    types = [item for item in (types or []) if item]
    windows = [item for item in (windows or []) if item]
    book = _campaign_rows()
    visible = [
        row
        for row in book
        if _row_in_view(
            row, geos=geos, spend=spend_bands, types=types, windows=windows, today=today
        )
    ]
    spend_rows = [
        row
        for row in book
        if _row_in_view(
            row,
            geos=geos,
            spend=spend_bands,
            types=types,
            windows=windows,
            today=today,
            skip="spend",
        )
    ]
    type_rows = [
        row
        for row in book
        if _row_in_view(
            row,
            geos=geos,
            spend=spend_bands,
            types=types,
            windows=windows,
            today=today,
            skip="type",
        )
    ]
    type_filters = _type_filters(book)
    by_type = {
        item["id"]: {
            "id": item["id"],
            "label": item["label"],
            "count": 0,
            "spend": 0,
        }
        for item in type_filters
    }
    by_spend = {
        item["id"]: {
            "id": item["id"],
            "label": item["label"],
            "count": 0,
            "spend": 0,
        }
        for item in SPEND_FILTERS
    }
    for row in type_rows:
        bucket = by_type.get(row["type"])
        if bucket:
            bucket["count"] += 1
            bucket["spend"] += row["spend"]
    for row in spend_rows:
        bucket = by_spend.get(row["spend_band"])
        if bucket:
            bucket["count"] += 1
            bucket["spend"] += row["spend"]
    coverage = _coverage_row(geos)
    alerts = _alerts(visible, today, coverage=coverage, geos=geos)
    slack = _slack()
    days_left = max(0, (_quarter_end(today) - today).days)
    total_spend = sum(int(row["spend"]) for row in visible)
    me = current_user()
    return {
        "as_of": today.isoformat(),
        "defaults": {"geo": me.get("region", "EMEA")},
        "copy": {
            "kicker": "SailPoint · Marketing",
            "title": "Campaigns",
            "kpi_pipeline": "Gap to target",
            "kpi_pipeline_hint": (
                f"vs {_money_short(total_spend)} in view · {days_left} days left in the quarter"
            ),
            "kpi_open": "Campaigns",
            "kpi_open_hint": "Match these filters",
            "kpi_week": "Ending this week",
            "kpi_week_hint": "Need a follow-up",
            "kpi_slack": "Slack",
            "kpi_slack_hint": "Open the feed",
            "empty": "No campaigns match these filters.",
            "unit": "campaigns",
        },
        "filters": {
            "spend": [
                {"id": item["id"], "label": item["label"]} for item in SPEND_FILTERS
            ],
            "types": type_filters,
            "windows": [dict(item) for item in TIME_FILTERS],
            "geos": [
                {"id": "AMER", "label": "AMER"},
                {"id": "EMEA", "label": "EMEA"},
                {"id": "APJ", "label": "APJ"},
            ],
        },
        "kpis": {
            "gap_usd": int(coverage.get("Gap to target (USD)") or 0),
            "spend": total_spend,
            "open_campaigns": len(visible),
            "closing_week": len(
                [row for row in visible if _in_time_window(row, "this_week", today)]
            ),
            "slack_work": len(slack),
            "days_left": days_left,
            "coverage": coverage.get("Coverage", ""),
        },
        "by_type": list(by_type.values()),
        "by_spend": list(by_spend.values()),
        "campaigns": visible,
        "tasks": _task_bar(visible, today, geos=geos),
        "notifications": alerts,
        "slack": slack,
        "connectors": [
            {"id": "salesforce", "label": "Salesforce campaigns", "status": "mock"},
            {"id": "chat", "label": "Chat artifacts", "status": "local"},
        ],
    }
