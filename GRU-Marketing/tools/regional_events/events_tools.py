"""Read-only tools for the Regional Events orchestrator."""

from __future__ import annotations

from google.adk.tools import ToolContext

from mktg_core import metrics
from mktg_core.connectors import accounts_by_id
from tools._shared._common import REGION_HELP, conn, parse_region


def get_unworked_accounts_by_city(region: str) -> str:
    """Accounts with no opportunity, grouped by city, with their intent topics.

    This is the starting point for deciding where to run a field event and what
    the session should be about.

    Args:
        region: {region_help}

    Returns:
        A markdown table of cities ranked by cluster size, showing the top
        intent keywords for each.
    """
    return metrics.accounts_without_opportunity(
        conn(), parse_region(region)).to_markdown()


def get_intent_themes(account_ids: str, min_intent_score: int) -> str:
    """What a set of accounts is researching, ranked by how many show each topic.

    Args:
        account_ids: Comma-separated account ids such as "ACC-001,ACC-002",
            or "all" to cover every account.
        min_intent_score: Ignore signals weaker than this, 0 to 100. Use 0 for
            no filter and 80 for strong signals only.

    Returns:
        A markdown table of intent keywords with account counts and scores.
    """
    ids = _parse_ids(account_ids)
    return metrics.intent_themes(conn(), ids, min_intent_score).to_markdown()


def find_accounts_in_city(city: str) -> str:
    """Look up accounts in a city, showing whether each has an opportunity.

    Use this after picking an event location, to get the account ids needed by
    the other tools.

    Args:
        city: City name, for example "Munich".

    Returns:
        A markdown table of accounts with their ids, size and opportunity status.
    """
    c = conn()
    with_opp = {o.account_id for o in c.sfdc.list_opportunities()}
    matches = [a for a in c.sfdc.list_accounts()
               if a.city.lower() == city.strip().lower()]
    if not matches:
        cities = sorted({a.city for a in c.sfdc.list_accounts()})
        return (f"No accounts found in {city!r}. Known cities: "
                f"{', '.join(cities)}.")

    lines = [f"### Accounts in {matches[0].city}", "",
             "| Account id | Name | Industry | Employees | Target account | "
             "Has opportunity |",
             "|---|---|---|---|---|---|"]
    for a in sorted(matches, key=lambda x: x.employee_count, reverse=True):
        lines.append(
            f"| {a.id} | {a.name} | {a.industry} | {a.employee_count:,} | "
            f"{'yes' if a.is_target_account else 'no'} | "
            f"{'yes' if a.id in with_opp else 'no'} |")
    return "\n".join(lines)


def get_buying_committee(account_ids: str) -> str:
    """Rank contacts at these accounts for event invitation.

    Scoring is a fixed rubric on seniority and job function, so the ranking is
    consistent and explainable. Judge any job titles that do not map cleanly
    onto the categories yourself.

    Args:
        account_ids: Comma-separated account ids such as "ACC-001,ACC-002".

    Returns:
        A markdown table of contacts sorted by fit score, with the rubric
        explained in the notes.
    """
    ids = _parse_ids(account_ids)
    if ids is None:
        return "Provide specific account ids for this tool, not 'all'."
    return metrics.buying_committee(conn(), ids).to_markdown()


def list_field_events() -> str:
    """All field events with their city, date, topic and registration count.

    Returns:
        A markdown table of events and their ids.
    """
    c = conn()
    lines = ["### Field events", "",
             "| Event id | Name | City | Region | Date | Topic | Registrations |",
             "|---|---|---|---|---|---|---|"]
    for event in c.events.list_events():
        attendees = c.events.list_attendees(event.id)
        lines.append(
            f"| {event.id} | {event.name} | {event.city} | {event.region.value} | "
            f"{event.event_date} | {event.topic} | {len(attendees)} |")
    return "\n".join(lines)


def get_event_attendees(event_id: str) -> str:
    """Who is registered for an event, and which account each belongs to.

    Args:
        event_id: The event id, for example "EVT-001". Use list_field_events
            first if you do not know it.

    Returns:
        A markdown table of attendees, plus the list of account ids in the
        room for use with the pipeline tool.
    """
    c = conn()
    attendees = c.events.list_attendees(event_id.strip())
    if not attendees:
        return f"No attendees found for event {event_id!r}."

    accounts = accounts_by_id(c.sfdc)
    contacts = {ct.id: ct for ct in c.sfdc.list_contacts()}

    lines = [f"### Attendees for {event_id}", "",
             "| Contact | Title | Account | Account id | City | Status |",
             "|---|---|---|---|---|---|"]
    for a in attendees:
        contact = contacts.get(a.contact_id)
        account = accounts.get(a.account_id)
        lines.append(
            f"| {contact.full_name if contact else '-'} "
            f"| {contact.title if contact else '-'} "
            f"| {account.name if account else '-'} | {a.account_id} "
            f"| {account.city if account else '-'} | {a.status} |")

    unique_accounts = sorted({a.account_id for a in attendees})
    lines += ["", f"{len(attendees)} registrations across "
                  f"{len(unique_accounts)} accounts.",
              "", f"Account ids in the room: {','.join(unique_accounts)}"]
    return "\n".join(lines)


def get_pipeline_in_accounts(account_ids: str) -> str:
    """Total open pipeline across a specific set of accounts.

    Use this for "pipeline in the room" at an event, after getting the account
    ids from get_event_attendees.

    Args:
        account_ids: Comma-separated account ids such as "ACC-001,ACC-002".

    Returns:
        A markdown table of pipeline per account, with the total and the
        accounts carrying nothing open called out in the notes.
    """
    ids = _parse_ids(account_ids)
    if ids is None:
        return "Provide specific account ids for this tool, not 'all'."
    return metrics.pipeline_in_accounts(conn(), ids).to_markdown()


def get_account_snapshot(account_id: str) -> str:
    """Everything known about one account, for writing a briefing.

    Pulls the firmographics, health score, open and closed opportunities,
    senior contacts, intent signals and recent content engagement into one
    view.

    Args:
        account_id: A single account id, for example "ACC-001".

    Returns:
        A markdown briefing pack for that account.
    """
    c = conn()
    account = accounts_by_id(c.sfdc).get(account_id.strip())
    if account is None:
        return f"No account found with id {account_id!r}."

    opps = [o for o in c.sfdc.list_opportunities() if o.account_id == account.id]
    contacts = c.sfdc.list_contacts([account.id])
    signals = sorted(c.sixsense.list_intent_signals([account.id]),
                     key=lambda s: s.intent_score, reverse=True)
    engagement = sorted(c.marketo.list_engagement_events([account.id]),
                        key=lambda e: e.occurred_on, reverse=True)

    health = account.health_score
    lines = [
        f"### {account.name} ({account.id})", "",
        f"- Industry: {account.industry}",
        f"- Location: {account.city}, {account.country} ({account.region.value})",
        f"- Size: {account.employee_count:,} employees, "
        f"${account.annual_revenue_usd:,} revenue",
        f"- Target account: {'yes' if account.is_target_account else 'no'}",
        f"- Gainsight health score: {health if health is not None else 'not a customer'}",
        "",
        "**Opportunities**",
    ]
    if opps:
        lines += ["", "| Name | Stage | Amount | Days open | Stalled |",
                  "|---|---|---|---|---|"]
        for o in sorted(opps, key=lambda x: x.amount_usd, reverse=True):
            lines.append(
                f"| {o.name} | {o.stage.value} | ${o.amount_usd:,} | "
                f"{o.days_in_pipeline} | {'yes' if o.is_stalled else 'no'} |")
        open_value = sum(o.amount_usd for o in opps if o.is_open)
        lines += ["", f"Open pipeline: ${open_value:,}."]
    else:
        lines.append("\nNo opportunities. This is an unworked account.")

    lines += ["", "**Key contacts**", "",
              "| Name | Title | Seniority | Function |", "|---|---|---|---|"]
    ranked = sorted(contacts, key=lambda ct: {
        "C-Level": 0, "VP": 1, "Director": 2, "Manager": 3, "Practitioner": 4
    }.get(ct.seniority, 5))
    for ct in ranked[:6]:
        lines.append(
            f"| {ct.full_name} | {ct.title} | {ct.seniority} | {ct.function} |")

    lines += ["", "**Intent signals**"]
    if signals:
        lines += ["", "| Keyword | Score | Buying stage | Trending |",
                  "|---|---|---|---|"]
        for s in signals[:6]:
            lines.append(
                f"| {s.keyword} | {s.intent_score} | {s.buying_stage} | "
                f"{'yes' if s.trending else 'no'} |")
    else:
        lines.append("\nNo intent signals recorded.")

    lines += ["", "**Recent content engagement**"]
    if engagement:
        lines += ["", "| Asset | Type | Date |", "|---|---|---|"]
        for e in engagement[:6]:
            lines.append(f"| {e.asset_name} | {e.asset_type} | {e.occurred_on} |")
    else:
        lines.append("\nNo recorded engagement.")

    return "\n".join(lines)


BRIEF_GROUPS = 3
BRIEF_DATA_KEY = "events_brief_data_{}"


def prepare_account_briefs(
    account_ids: str, event_id: str, tool_context: ToolContext
) -> str:
    """Gather the raw material for account briefs and split it for parallel writing.

    Call this once before any briefs are written. It fetches every account's
    full snapshot in one pass and divides the work into groups, so the writing
    can happen simultaneously rather than one account at a time.

    Args:
        account_ids: Comma-separated account ids, or "" to use the event instead.
        event_id: An event id such as "EVT-001" to brief on everyone attending,
            or "" if account_ids was given.

    Returns:
        How many accounts were found and how they were divided.
    """
    c = conn()
    ids = _parse_ids(account_ids) or []

    if not ids and event_id.strip():
        attendees = c.events.list_attendees(event_id.strip())
        if not attendees:
            return f"No attendees found for event {event_id!r}."
        ids = sorted({a.account_id for a in attendees})

    if not ids:
        return ("Provide either account_ids or an event_id so I know which "
                "accounts to brief on.")

    known = accounts_by_id(c.sfdc)
    missing = [i for i in ids if i not in known]
    ids = [i for i in ids if i in known]
    if not ids:
        return f"None of those account ids exist. Unknown: {', '.join(missing)}."

    snapshots = [get_account_snapshot(account_id) for account_id in ids]

    # Round-robin rather than contiguous slices, so no single group ends up
    # with all the large accounts and becomes the slow one.
    groups: list[list[str]] = [[] for _ in range(BRIEF_GROUPS)]
    for index, snapshot in enumerate(snapshots):
        groups[index % BRIEF_GROUPS].append(snapshot)

    for number, group in enumerate(groups, start=1):
        tool_context.state[BRIEF_DATA_KEY.format(number)] = (
            "\n\n---\n\n".join(group) if group else "")

    sizes = ", ".join(
        f"group {n}: {len(g)}" for n, g in enumerate(groups, start=1) if g)
    note = (f" Ignored {len(missing)} unknown ids." if missing else "")
    return (f"Prepared briefing data for {len(ids)} accounts, split across "
            f"{sum(1 for g in groups if g)} groups ({sizes}).{note}")


def _parse_ids(value: str) -> list[str] | None:
    """Comma-separated ids into a list, or None for 'all'."""
    cleaned = (value or "").strip()
    if cleaned.lower() in {"all", ""}:
        return None
    return [part.strip() for part in cleaned.split(",") if part.strip()]


for _fn in (get_unworked_accounts_by_city,):
    _fn.__doc__ = _fn.__doc__.replace("{region_help}", REGION_HELP)


EVENTS_TOOLS = [
    get_unworked_accounts_by_city,
    get_intent_themes,
    find_accounts_in_city,
    get_buying_committee,
    list_field_events,
    get_event_attendees,
    get_pipeline_in_accounts,
    get_account_snapshot,
]
BRIEF_TOOLS = [prepare_account_briefs]
