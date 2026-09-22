"""Map internal child authors to marketer-facing status copy."""

from __future__ import annotations

# The root router speaks first and last. Before it has picked a team there is
# nothing to hand off, so it carries the generic line rather than the name of
# a specialist.
THINKING_LABEL = "James is thinking…"

STATUS_BY_AUTHOR = {
    "marketing_orchestrator": THINKING_LABEL,
    "analysis_orchestrator": "Handing this to analysis…",
    "analysis_campaign_performance": "Pulling campaign results…",
    "analysis_improvement_recommender": "Working out where to move budget…",
    "analysis_pipeline_health": "Checking pipeline coverage…",
    "analysis_asset_influence": "Ranking content influence…",
    "analysis_pipeline_deck": "Building the pipeline deck…",
    "analysis_pipeline_deck_analyst": "Analysing pipeline data for the slides…",
    "analysis_pipeline_deck_writer": "Writing the pipeline slides…",
    "analysis_demand_council_deck": "Building the demand council deck…",
    "analysis_demand_council_analyst": "Analysing demand data for the slides…",
    "analysis_demand_council_writer": "Writing the demand council slides…",
    "events_orchestrator": "Handing this to regional events…",
    "events_location_topic": "Finding where to run the event…",
    "events_attendee_targeting": "Building the invitation list…",
    "events_account_briefs": "Writing account briefs…",
    "events_brief_preparer": "Gathering account snapshots…",
    "events_brief_writers": "Drafting the briefs in parallel…",
    "events_brief_merger": "Merging the briefing pack…",
    "events_pipeline_in_room": "Totalling pipeline in the room…",
    "mops_orchestrator": "Running the marketing ops request…",
    "mops_list_load": "Loading the lead list…",
    "mops_list_load_reader": "Reading the lead file…",
    "mops_list_load_cleaner": "Cleaning the lead rows…",
    "mops_list_load_validator": "Validating the lead rows…",
    "mops_list_load_loader": "Loading into Marketo…",
    "campaign_design_orchestrator": "Handing this to campaign design…",
    "campaign_ideation": "Developing campaign ideas…",
    "campaign_brief_builder": "Building the campaign brief…",
    "campaign_brief_deck": "Building the campaign PowerPoint…",
    "campaign_brief_deck_analyst": "Writing the campaign brief for the slides…",
    "campaign_brief_deck_writer": "Writing the campaign slides…",
    "campaign_battlecard": "Building the competitive battlecard…",
    "abm_orchestrator": "Handing this to account-based marketing…",
    "abm_account_selection": "Ranking target accounts…",
    "abm_account_intel": "Researching the account…",
    "abm_gap_value": "Mapping gaps and quantified value…",
    "abm_messaging": "Drafting persona messaging…",
    "abm_multichannel_package": "Building the multi-channel ABM play…",
    "content_orchestrator": "Handing this to content generation…",
    "content_anchor_asset": "Writing the anchor asset…",
    "content_localization": "Localising the content…",
    "content_asset_grid": "Building the asset grid…",
    "content_campaign_variant": "Creating campaign content variants…",
    "brand_orchestrator": "Handing this to brand intelligence…",
    "brand_social_sentiment": "Analysing social sentiment…",
    "brand_share_of_voice": "Measuring share of voice…",
    "brand_news_trends": "Monitoring news and trends…",
    "brand_rapid_response": "Building the rapid-response package…",
}


def status_for_author(author: str) -> str | None:
    """Return a progress label, or None when the author is not shown."""
    return STATUS_BY_AUTHOR.get(author)
