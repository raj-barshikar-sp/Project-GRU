"""Every calculation in the system.

No agent does arithmetic. Functions here return a `MetricTable`, the agent
receives it as markdown and explains it. If a number appears in an answer, it
came from this package.
"""

from .attribution import asset_influence
from .abm_scoring import account_tiering
from .brand_metrics import news_trends, sentiment_summary, share_of_voice
from .campaigns import (
    campaign_performance,
    funnel_by_type,
    spend_efficiency_outliers,
    week_over_week,
)
from .geo import accounts_without_opportunity, buying_committee, intent_themes
from .pipeline import (
    closed_won_rate,
    coverage_by_region,
    pipeline_in_accounts,
    stage_distribution,
    stage_movement,
    stalled_deals,
)
from .value import gap_value_map

__all__ = [
    "account_tiering",
    "accounts_without_opportunity",
    "asset_influence",
    "buying_committee",
    "campaign_performance",
    "closed_won_rate",
    "coverage_by_region",
    "funnel_by_type",
    "gap_value_map",
    "intent_themes",
    "news_trends",
    "pipeline_in_accounts",
    "sentiment_summary",
    "share_of_voice",
    "spend_efficiency_outliers",
    "stage_distribution",
    "stage_movement",
    "stalled_deals",
    "week_over_week",
]
