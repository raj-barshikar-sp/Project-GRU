"""Tools for the Marketing Ops orchestrator.

These are the only tools in the system that write anything. Every write is
mocked in the POC: the tool returns a realistic result and describes what it
would have sent, without touching a real Salesforce or Marketo.

The list-load tools pass their working data through ADK session state rather
than through the model. That is deliberate. Handing 500 CSV rows back and forth
through a prompt is slow, expensive, and invites the model to "helpfully" edit
someone's email address.
"""

from __future__ import annotations

import re
from datetime import date

from google.adk.tools import ToolContext

from mktg_core.connectors import get_connectors
from mktg_core.contracts import (
    CampaignSpec,
    CampaignType,
    ListLoadIssue,
    ListLoadReport,
    Region,
    SegmentFilter,
)
from mktg_core.contracts.marketing_ops import UPLOADED_LEAD_FILES_STATE
from tools._shared._common import conn

# Session state keys. Namespaced per the repo conventions so they cannot
# collide with another orchestrator's keys.
RAW_ROWS = "mops_list_load_raw_rows"
CLEAN_ROWS = "mops_list_load_clean_rows"
VALID_ROWS = "mops_list_load_valid_rows"

# ISO codes that turn up in event exports and have to become full names before
# Marketo will accept them.
COUNTRY_CODES = {
    "DE": "Germany", "FR": "France", "IT": "Italy", "NL": "Netherlands",
    "AT": "Austria", "ES": "Spain", "BE": "Belgium", "CH": "Switzerland",
    "GB": "United Kingdom", "UK": "United Kingdom", "IE": "Ireland",
    "US": "United States", "USA": "United States", "CA": "Canada",
    "SG": "Singapore", "AU": "Australia", "JP": "Japan", "IN": "India",
}
REQUIRED_COLUMNS = ["First Name", "Last Name", "Email", "Company", "Country"]
# Addresses that must never be loaded as marketing leads.
SUPPRESSED_DOMAINS = {"gru-internal.com", "gru.com"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


# --- Salesforce campaign creation ----------------------------------------

def create_sfdc_campaign(
    name: str,
    campaign_type: str,
    region: str,
    start_date: str,
    end_date: str,
    budget_usd: int,
    owner_email: str,
    description: str,
) -> str:
    """Create a Salesforce campaign record.

    Mocked in this build: nothing is written to a real Salesforce org.

    The name must follow the convention REGION-TYPE-YYYYQN-Description, for
    example "EMEA-Webinar-2026Q3-Zero-Trust". If the name you are given does
    not follow it, fix the name before calling this tool.

    Args:
        name: Campaign name following the naming convention.
        campaign_type: One of Webinar, Field Event, Paid Search, Paid Social,
            Content Syndication, Email Nurture, Tradeshow.
        region: AMER, EMEA or APJ.
        start_date: Start date as YYYY-MM-DD.
        end_date: End date as YYYY-MM-DD.
        budget_usd: Budget in whole US dollars.
        owner_email: Email address of the campaign owner.
        description: One or two sentences on the campaign's purpose.

    Returns:
        A confirmation with the new campaign id, or an explanation of what
        was wrong with the inputs.
    """
    try:
        spec = CampaignSpec(
            name=name,
            type=CampaignType(campaign_type.strip()),
            region=Region(region.strip().upper()),
            start_date=date.fromisoformat(start_date.strip()),
            end_date=date.fromisoformat(end_date.strip()),
            budget_usd=int(budget_usd),
            owner_email=owner_email.strip(),
            description=description,
        )
    except ValueError as exc:
        valid_types = ", ".join(t.value for t in CampaignType)
        return (f"Could not create the campaign: {exc}. "
                f"Valid campaign types are: {valid_types}. "
                f"Regions are AMER, EMEA, APJ. Dates must be YYYY-MM-DD.")

    if spec.end_date < spec.start_date:
        return (f"Could not create the campaign: end date {spec.end_date} is "
                f"before start date {spec.start_date}.")

    naming = re.match(r"^(AMER|EMEA|APJ)-[A-Za-z ]+-\d{4}Q[1-4]-.+", spec.name)
    warning = ""
    if not naming:
        warning = ("\n\nNote: the name does not match the convention "
                   "REGION-TYPE-YYYYQN-Description. It was created anyway, "
                   "but consider renaming it.")

    result = get_connectors().sfdc.create_campaign(spec)
    assumptions = [
        f"Type: {spec.type.value}",
        f"Region: {spec.region.value}",
        f"Dates: {spec.start_date.isoformat()} to {spec.end_date.isoformat()}",
        f"Budget: {spec.budget_usd} USD",
        f"Owner: {spec.owner_email}",
    ]
    if warning:
        assumptions.append(
            "The name does not match the convention "
            "REGION-TYPE-YYYYQN-Description. It was created anyway, "
            "but consider renaming it."
        )
    return (
        "## Receipt\n"
        "Status: Would create. Nothing was written to a real Salesforce org. "
        "This is a mock.\n"
        f"Id: {result.campaign_id}\n"
        f"Name: {spec.name}\n"
        f"Type: {spec.type.value}\n"
        f"Region: {spec.region.value}\n"
        f"Dates: {spec.start_date.isoformat()} to {spec.end_date.isoformat()}\n"
        f"Budget: {spec.budget_usd} USD\n\n"
        "## Assumptions\n"
        + "\n".join(f"- {item}" for item in assumptions)
    )


# --- 6sense segment building ---------------------------------------------

def build_6sense_segment(
    segment_name: str,
    industries: str,
    regions: str,
    countries: str,
    intent_keywords: str,
    min_intent_score: int,
    min_employee_count: int,
    target_accounts_only: bool,
) -> str:
    """Build a 6sense account segment from an explicit set of filters.

    Work out the filters from the user's request first, then call this. For
    example "fintech accounts surging on Zero Trust in EMEA" becomes
    industries="Financial Services", regions="EMEA",
    intent_keywords="Zero Trust", min_intent_score=80.

    Args:
        segment_name: A descriptive name for the segment.
        industries: Comma-separated industries, or "" for any. Valid values are
            Financial Services, Technology, Healthcare, Manufacturing, Retail,
            Public Sector.
        regions: Comma-separated regions from AMER, EMEA, APJ, or "" for any.
        countries: Comma-separated full country names, or "" for any.
        intent_keywords: Comma-separated intent keywords, or "" for any.
        min_intent_score: Minimum intent score from 0 to 100. Use 80 for
            "surging" or "high intent", 0 for no filter.
        min_employee_count: Minimum company headcount, or 0 for no filter.
        target_accounts_only: True to restrict to named target accounts.

    Returns:
        The segment id, how many accounts matched, and an echo of the filters
        applied so the user can check them.
    """
    def split(value: str) -> list[str]:
        return [p.strip() for p in (value or "").split(",") if p.strip()]

    try:
        region_values = [Region(r.upper()) for r in split(regions)]
    except ValueError:
        return f"Unknown region in {regions!r}. Use AMER, EMEA or APJ."

    filters = SegmentFilter(
        industries=split(industries),
        regions=region_values,
        countries=split(countries),
        intent_keywords=split(intent_keywords),
        min_intent_score=int(min_intent_score),
        min_employee_count=int(min_employee_count),
        target_accounts_only=bool(target_accounts_only),
    )

    c = conn()
    result = c.sixsense.build_segment(segment_name, filters, c.sfdc.list_accounts())

    if result.account_count == 0:
        return (f"Segment '{segment_name}' matched 0 accounts.\n"
                f"Filters applied: {result.filter_summary}\n\n"
                f"The filters are probably too narrow. Consider lowering "
                f"min_intent_score or dropping a filter.")

    accounts = {a.id: a for a in c.sfdc.list_accounts()}
    sample = [accounts[i].name for i in result.account_ids[:8] if i in accounts]

    return (
        f"MOCK: would create 6sense segment '{result.name}'.\n\n"
        f"- Segment id: {result.segment_id}\n"
        f"- Name: {result.name}\n"
        f"- Accounts matched: {result.account_count}\n"
        f"- Filters applied: {result.filter_summary}\n"
        f"- Sample accounts: {', '.join(sample)}"
        + (f" and {result.account_count - len(sample)} more"
           if result.account_count > len(sample) else "")
        + "\n\nNothing was written to a real 6sense instance. This is a mock."
    )


def deploy_segment_to_marketo(segment_id: str, segment_name: str) -> str:
    """Push a 6sense segment into Marketo as a smart list.

    Mocked in this build. Run build_6sense_segment first to get the id.

    Args:
        segment_id: The 6sense segment id, for example "SEG-MOCK-12345".
        segment_name: The segment name, used to name the Marketo list.

    Returns:
        The Marketo list id and how many contacts would be pushed.
    """
    c = conn()
    # Contact count comes from the accounts in the segment. In the mock the
    # segment is not persisted, so we approximate from all contacts at the
    # matching accounts; a live 6sense connector would return this directly.
    contact_count = len(c.sfdc.list_contacts())
    result = c.marketo.deploy_segment(segment_id.strip(), segment_name.strip(),
                                      contact_count)
    return (f"{result.message}\n\n"
            f"- Marketo list id: {result.marketo_list_id}\n"
            f"- Contacts: {result.contacts_pushed:,}")


# --- The list load chain --------------------------------------------------

def read_lead_file(filename: str, tool_context: ToolContext) -> str:
    """Step 1 of the list load: open the file and check its headers.

    Args:
        filename: The CSV file to load, for example "event_leads_munich.csv".

    Returns:
        The row count, the headers found, and whether any required column is
        missing.
    """
    clean_filename = filename.strip()
    uploaded = tool_context.state.get(UPLOADED_LEAD_FILES_STATE, {})
    rows = uploaded.get(clean_filename) if isinstance(uploaded, dict) else None
    if rows is None:
        try:
            rows = conn().marketo.read_lead_csv(clean_filename)
        except FileNotFoundError:
            return (f"No file named {filename!r}. The sample file available is "
                    f"'event_leads_munich.csv'.")

    if not rows:
        return f"{filename} is empty."

    headers = list(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]

    tool_context.state[RAW_ROWS] = rows

    report = ListLoadReport(
        stage="1. Read file",
        rows_in=len(rows),
        rows_out=len(rows),
        notes=[f"Headers found: {', '.join(headers)}"],
    )
    if missing:
        report.notes.append(
            f"MISSING REQUIRED COLUMNS: {', '.join(missing)}. "
            "The load cannot proceed without these.")
    else:
        report.notes.append("All required columns are present.")

    return report.to_markdown()


def clean_lead_rows(tool_context: ToolContext) -> str:
    """Step 2 of the list load: normalise the data.

    Trims whitespace, lowercases email addresses and expands ISO country codes
    into the full names Marketo expects. Nothing is rejected at this stage.

    Returns:
        A report of what was changed.
    """
    rows = tool_context.state.get(RAW_ROWS)
    if not rows:
        return "No rows in progress. Run read_lead_file first."

    changes: list[str] = []
    cleaned: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=2):  # row 1 is the header
        new_row = {k: (v or "").strip() for k, v in row.items()}

        email = new_row.get("Email", "")
        if email and email != email.lower():
            changes.append(f"Row {index}: lowercased email")
            new_row["Email"] = email.lower()

        country = new_row.get("Country", "")
        if country.upper() in COUNTRY_CODES:
            expanded = COUNTRY_CODES[country.upper()]
            changes.append(f"Row {index}: country {country} -> {expanded}")
            new_row["Country"] = expanded

        for key, value in row.items():
            if value and value != value.strip():
                changes.append(f"Row {index}: trimmed whitespace in {key}")

        cleaned.append(new_row)

    tool_context.state[CLEAN_ROWS] = cleaned

    report = ListLoadReport(
        stage="2. Clean and normalise",
        rows_in=len(rows),
        rows_out=len(cleaned),
        notes=changes[:20] or ["Nothing needed changing."],
    )
    if len(changes) > 20:
        report.notes.append(f"...and {len(changes) - 20} further changes.")
    return report.to_markdown()


def validate_lead_rows(tool_context: ToolContext) -> str:
    """Step 3 of the list load: reject rows that must not be uploaded.

    Checks for missing required fields, malformed email addresses, duplicate
    email addresses and internal addresses that should be suppressed.

    Returns:
        A table of every rejected row with the reason, and the count that
        survived.
    """
    rows = tool_context.state.get(CLEAN_ROWS)
    if not rows:
        return "No cleaned rows in progress. Run clean_lead_rows first."

    issues: list[ListLoadIssue] = []
    valid: list[dict[str, str]] = []
    seen_emails: set[str] = set()

    for index, row in enumerate(rows, start=2):
        row_issues: list[ListLoadIssue] = []

        for column in REQUIRED_COLUMNS:
            if not row.get(column):
                row_issues.append(ListLoadIssue(
                    row_number=index, column=column, problem="required field is empty"))

        email = row.get("Email", "")
        if email:
            if not EMAIL_PATTERN.match(email):
                row_issues.append(ListLoadIssue(
                    row_number=index, column="Email",
                    problem=f"not a valid email address: {email!r}"))
            else:
                domain = email.split("@")[1]
                if domain in SUPPRESSED_DOMAINS:
                    row_issues.append(ListLoadIssue(
                        row_number=index, column="Email",
                        problem=f"internal domain {domain} is suppressed"))
                elif email in seen_emails:
                    row_issues.append(ListLoadIssue(
                        row_number=index, column="Email",
                        problem=f"duplicate of an earlier row: {email}"))
                else:
                    seen_emails.add(email)

        if row_issues:
            issues.extend(row_issues)
        else:
            valid.append(row)

    tool_context.state[VALID_ROWS] = valid

    report = ListLoadReport(
        stage="3. Validate",
        rows_in=len(rows),
        rows_out=len(valid),
        issues=issues,
        notes=[
            f"{len(rows) - len(valid)} rows rejected, {len(valid)} ready to load.",
            "Rejected rows are not uploaded. Nothing is silently fixed.",
        ],
    )
    return report.to_markdown()


def load_cleaned_list(list_name: str, tool_context: ToolContext) -> str:
    """Step 4 of the list load: upload the surviving rows into Marketo.

    Mocked in this build. Only rows that passed validation are loaded.

    Args:
        list_name: Name for the new Marketo static list.

    Returns:
        The Marketo list id and the number of rows loaded.
    """
    rows = tool_context.state.get(VALID_ROWS)
    if rows is None:
        return "No validated rows in progress. Run validate_lead_rows first."
    if not rows:
        return ("Every row failed validation, so there is nothing to load. "
                "Fix the source file and start again.")

    result = conn().marketo.load_list(list_name.strip(), rows)
    countries = sorted({r.get("Country", "") for r in rows if r.get("Country")})
    return (
        f"{result['message']}\n\n"
        f"- Marketo list id: {result['marketo_list_id']}\n"
        f"- Rows loaded: {result['rows_loaded']}\n"
        f"- Countries represented: {', '.join(countries)}"
    )


MOPS_TOOLS = [
    create_sfdc_campaign,
    build_6sense_segment,
    deploy_segment_to_marketo,
]
LIST_LOAD_TOOLS = [
    read_lead_file,
    clean_lead_rows,
    validate_lead_rows,
    load_cleaned_list,
]
