"""Campaign performance and the recommendations that follow from it.

These two are separate agents rather than one because they answer genuinely
different questions. "How did we do?" wants an accurate read of what happened.
"What should we change?" wants an argument. Splitting them keeps the analysis
honest and stops every performance question turning into unsolicited advice.

The recommender reads the analyst's output from session state, so a user who
asks both questions in a row does not pay for the same analysis twice.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.analysis.analysis_tools import (
    get_campaign_performance,
    get_funnel_by_campaign_type,
    get_pipeline_coverage,
    get_spend_efficiency_outliers,
    get_week_over_week_movement,
)

from ..prompts import (
    ANALYSIS_CAMPAIGN_PERFORMANCE_DESCRIPTION,
    ANALYSIS_CAMPAIGN_PERFORMANCE_INSTRUCTION,
    ANALYSIS_IMPROVEMENT_RECOMMENDER_DESCRIPTION,
    ANALYSIS_IMPROVEMENT_RECOMMENDER_INSTRUCTION,
)

campaign_performance_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_campaign_performance",
    description=ANALYSIS_CAMPAIGN_PERFORMANCE_DESCRIPTION,
    instruction=ANALYSIS_CAMPAIGN_PERFORMANCE_INSTRUCTION,
    tools=[
        get_pipeline_coverage,
        get_campaign_performance,
        get_funnel_by_campaign_type,
        get_week_over_week_movement,
    ],
    output_key="analysis_campaign_performance",
)


improvement_recommender = LlmAgent(
    model=DEFAULT_MODEL,
    name="analysis_improvement_recommender",
    description=ANALYSIS_IMPROVEMENT_RECOMMENDER_DESCRIPTION,
    instruction=ANALYSIS_IMPROVEMENT_RECOMMENDER_INSTRUCTION,
    tools=[
        get_spend_efficiency_outliers,
        get_pipeline_coverage,
        get_campaign_performance,
        get_funnel_by_campaign_type,
    ],
    output_key="analysis_recommendations",
)
