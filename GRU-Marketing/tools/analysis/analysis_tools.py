"""Read-only tools for the Analysis orchestrator.

Each one runs a calculation from `mktg_core.metrics` and hands back a finished
markdown table. No tool here asks the model to work anything out.
"""

from __future__ import annotations

from mktg_core import metrics
from tools._shared._common import REGION_HELP, conn, parse_region


def get_campaign_performance(region: str) -> str:
    """Spend, funnel counts and cost per opportunity for every campaign.

    Use this for questions about how campaigns that already ran performed.

    Args:
        region: {region_help}

    Returns:
        A markdown table sorted by cost per opportunity, cheapest first.
    """
    return metrics.campaign_performance(conn(), parse_region(region)).to_markdown()


def get_funnel_by_campaign_type(region: str) -> str:
    """The same funnel aggregated by channel rather than by individual campaign.

    Use this when the question is about which channels work, rather than which
    specific campaigns did.

    Args:
        region: {region_help}

    Returns:
        A markdown table of spend and conversion per campaign type.
    """
    return metrics.funnel_by_type(conn(), parse_region(region)).to_markdown()


def get_week_over_week_movement(region: str) -> str:
    """How each campaign's leads, MQLs and opportunities changed in seven days.

    Args:
        region: {region_help}

    Returns:
        A markdown table of week-over-week deltas, biggest MQL gain first.
    """
    return metrics.week_over_week(conn(), parse_region(region)).to_markdown()


def get_spend_efficiency_outliers() -> str:
    """The best and worst campaigns by cost per opportunity.

    Use this when asked how to improve performance or where to move budget.
    The notes on the table quantify what a budget shift would buy.

    Returns:
        A markdown table of the most and least efficient campaigns.
    """
    return metrics.spend_efficiency_outliers(conn()).to_markdown()


def get_pipeline_coverage() -> str:
    """Open pipeline against quarterly target for every region.

    This is the starting point for any pipeline health question. It shows which
    regions clear the 2x coverage bar and the gap for those that do not.

    Returns:
        A markdown table of coverage by region, with a total row.
    """
    return metrics.coverage_by_region(conn()).to_markdown()


def get_stage_distribution(region: str) -> str:
    """How open pipeline value and deal count sit across the stages.

    Args:
        region: {region_help}

    Returns:
        A markdown table of opportunities and value per stage.
    """
    return metrics.stage_distribution(conn(), parse_region(region)).to_markdown()


def get_stalled_deals(region: str) -> str:
    """Open deals over 60 days old that have not changed stage in a week.

    Args:
        region: {region_help}

    Returns:
        A markdown table of stalled deals, largest first, with total value
        at risk in the notes.
    """
    return metrics.stalled_deals(conn(), parse_region(region)).to_markdown()


def get_stage_movement(region: str) -> str:
    """How many open deals advanced, held or slipped back in the past week.

    Args:
        region: {region_help}

    Returns:
        A markdown table of movement counts and shares.
    """
    return metrics.stage_movement(conn(), parse_region(region)).to_markdown()


def get_asset_influence() -> str:
    """Which content assets correlate with opportunities progressing.

    Ranks assets by lift over the baseline progression rate. Use this for
    questions about what content is working or moving the needle.

    Returns:
        A markdown table of assets ranked by lift, with the correlation
        caveat stated in the notes.
    """
    return metrics.asset_influence(conn()).to_markdown()


# The docstrings are what the model reads to decide which tool to call, so the
# region placeholder is filled in rather than left as literal braces.
for _fn in (get_campaign_performance, get_funnel_by_campaign_type,
            get_week_over_week_movement, get_stage_distribution,
            get_stalled_deals, get_stage_movement):
    _fn.__doc__ = _fn.__doc__.replace("{region_help}", REGION_HELP)


ANALYSIS_TOOLS = [
    get_campaign_performance,
    get_funnel_by_campaign_type,
    get_week_over_week_movement,
    get_spend_efficiency_outliers,
    get_pipeline_coverage,
    get_stage_distribution,
    get_stalled_deals,
    get_stage_movement,
    get_asset_influence,
]
