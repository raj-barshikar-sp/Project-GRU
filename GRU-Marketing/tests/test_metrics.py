"""Tests for the calculation layer.

These matter more than they look. The whole design rests on agents never doing
arithmetic, which is only safe if the arithmetic underneath is right. Each test
recomputes the answer independently from the fixtures rather than asserting a
hardcoded number, so the tests stay honest if the sample data is regenerated.

A handful of assertions do pin the planted stories, because those stories are
what the demo depends on.
"""

from __future__ import annotations

import pytest

from mktg_core.connectors import get_connectors
from mktg_core.contracts import OppStage, Region
from mktg_core.metrics import (
    accounts_without_opportunity,
    asset_influence,
    buying_committee,
    campaign_performance,
    coverage_by_region,
    funnel_by_type,
    intent_themes,
    pipeline_in_accounts,
    spend_efficiency_outliers,
    stage_distribution,
    stage_movement,
    stalled_deals,
    week_over_week,
)


@pytest.fixture(scope="module")
def conn():
    return get_connectors()


def row_for(table, column, value):
    return next(r for r in table.rows if r[column] == value)


# --- coverage -------------------------------------------------------------

def test_coverage_matches_hand_computed_totals(conn):
    table = coverage_by_region(conn)
    opps = conn.sfdc.list_opportunities()
    targets = conn.tableau.all_targets()

    for region in Region:
        expected = sum(
            o.amount_usd for o in opps if o.owner_region == region and o.is_open
        )
        row = row_for(table, "Region", region.value)
        assert row["Open pipeline (USD)"] == expected
        assert row["Coverage"] == f"{round(expected / targets[region.value], 2)}x"


def test_coverage_total_row_is_the_sum_of_the_regions(conn):
    table = coverage_by_region(conn)
    regions = [r for r in table.rows if r["Region"] != "TOTAL"]
    total = row_for(table, "Region", "TOTAL")
    assert total["Open pipeline (USD)"] == sum(
        r["Open pipeline (USD)"] for r in regions)


def test_coverage_excludes_closed_opportunities(conn):
    table = coverage_by_region(conn)
    all_value = sum(o.amount_usd for o in conn.sfdc.list_opportunities())
    total = row_for(table, "Region", "TOTAL")["Open pipeline (USD)"]
    assert total < all_value, "closed deals must not count towards coverage"


def test_planted_story_emea_is_under_target_and_others_are_not(conn):
    """The demo's opening line depends on this being true."""
    table = coverage_by_region(conn)
    assert row_for(table, "Region", "EMEA")["Meets 2x target"] is False
    assert row_for(table, "Region", "AMER")["Meets 2x target"] is True
    assert row_for(table, "Region", "APJ")["Meets 2x target"] is True


# --- stages and stalled deals --------------------------------------------

def test_stage_distribution_shares_sum_to_100(conn):
    table = stage_distribution(conn)
    total = sum(float(r["Share of pipeline"].rstrip("%")) for r in table.rows)
    assert total == pytest.approx(100.0, abs=0.5)


def test_stage_distribution_counts_match_the_raw_opportunities(conn):
    table = stage_distribution(conn, Region.EMEA)
    opps = [o for o in conn.sfdc.list_opportunities(Region.EMEA) if o.is_open]
    assert sum(r["Opps"] for r in table.rows) == len(opps)


def test_stalled_needs_both_age_and_no_movement(conn):
    """An old deal that moved is not stalled, and a young stuck deal is not either."""
    stalled_ids = {
        o.id for o in conn.sfdc.list_opportunities() if o.is_stalled
    }
    for opp in conn.sfdc.list_opportunities():
        if opp.id in stalled_ids:
            assert opp.is_open
            assert opp.days_in_pipeline > 60
            assert opp.stage_one_week_ago == opp.stage
        elif opp.is_open and opp.days_in_pipeline > 60:
            assert opp.stage_one_week_ago != opp.stage


def test_stalled_deals_are_sorted_largest_first(conn):
    table = stalled_deals(conn)
    amounts = [r["Amount (USD)"] for r in table.rows]
    assert amounts == sorted(amounts, reverse=True)


def test_planted_story_there_are_stalled_deals_to_talk_about(conn):
    assert len(stalled_deals(conn).rows) >= 5


def test_stage_movement_buckets_cover_every_open_opp(conn):
    table = stage_movement(conn)
    opps = [o for o in conn.sfdc.list_opportunities()
            if o.is_open and o.stage_one_week_ago is not None]
    assert sum(r["Opps"] for r in table.rows) == len(opps)


# --- campaigns ------------------------------------------------------------

def test_cost_per_opp_is_spend_divided_by_opps(conn):
    table = campaign_performance(conn)
    for campaign in conn.sfdc.list_campaigns():
        row = row_for(table, "Campaign", campaign.name)
        if campaign.opps_created:
            assert row["Cost per opp (USD)"] == int(
                campaign.spend_usd / campaign.opps_created)
        else:
            assert row["Cost per opp (USD)"] is None


def test_campaigns_sorted_cheapest_per_opp_first(conn):
    table = campaign_performance(conn)
    costs = [r["Cost per opp (USD)"] for r in table.rows
             if r["Cost per opp (USD)"] is not None]
    assert costs == sorted(costs)


def test_funnel_by_type_spend_reconciles_with_campaigns(conn):
    table = funnel_by_type(conn)
    assert sum(r["Spend (USD)"] for r in table.rows) == sum(
        c.spend_usd for c in conn.sfdc.list_campaigns())


def test_week_over_week_deltas_are_signed_correctly(conn):
    table = week_over_week(conn)
    for campaign in conn.sfdc.list_campaigns():
        row = row_for(table, "Campaign", campaign.name)
        diff = campaign.mqls - campaign.mqls_one_week_ago
        if diff > 0:
            assert row["MQLs WoW"].startswith("+")
        elif diff == 0:
            assert row["MQLs WoW"].startswith("0")


def test_planted_story_paid_social_is_the_worst_buy(conn):
    """The budget-shift recommendation hangs on this outlier being visible."""
    table = spend_efficiency_outliers(conn)
    worst = [r for r in table.rows if r["Band"] == "Least efficient"]
    best = [r for r in table.rows if r["Band"] == "Most efficient"]
    assert "Paid Social - Cloud Security Always On" in {
        r["Campaign"] for r in worst}
    assert "Webinar - Zero Trust Maturity" in {r["Campaign"] for r in best}
    assert worst[0]["Cost per opp (USD)"] > 10 * best[0]["Cost per opp (USD)"]


# --- attribution ----------------------------------------------------------

def test_asset_influence_progressed_never_exceeds_touched(conn):
    for row in asset_influence(conn).rows:
        assert row["Accounts progressed"] <= row["Accounts touched"]


def test_asset_influence_sorted_by_lift(conn):
    lifts = [float(r["Lift vs baseline"].rstrip("x"))
             for r in asset_influence(conn).rows]
    assert lifts == sorted(lifts, reverse=True)


def test_planted_story_zero_trust_guide_beats_the_brochure(conn):
    """The asset agent should be able to separate signal from noise."""
    rows = {r["Asset"]: r for r in asset_influence(conn).rows}
    guide = float(rows["Zero Trust Maturity Guide"]["Lift vs baseline"].rstrip("x"))
    brochure = float(rows["Company Overview Brochure"]["Lift vs baseline"].rstrip("x"))
    assert guide > brochure
    assert guide > 1.0, "the influential asset should beat the baseline"


# --- geo and events -------------------------------------------------------

def test_no_opp_accounts_really_have_no_opportunity(conn):
    table = accounts_without_opportunity(conn)
    with_opp = {o.account_id for o in conn.sfdc.list_opportunities()}
    accounts = {a.city: a for a in conn.sfdc.list_accounts()}
    counted = sum(r["Accounts with no opp"] for r in table.rows)
    expected = len([a for a in conn.sfdc.list_accounts() if a.id not in with_opp])
    assert counted == expected
    assert accounts  # sanity


def test_planted_story_germany_is_the_best_event_location(conn):
    """The events agent should pick a German city over Singapore."""
    table = accounts_without_opportunity(conn, Region.EMEA)
    top = table.rows[0]
    assert top["City"] in {"Munich", "Frankfurt"}
    assert top["Accounts with no opp"] >= 4
    assert "Zero Trust" in top["Top intent keywords"]


def test_intent_themes_respect_the_score_floor(conn):
    table = intent_themes(conn, min_score=80)
    for row in table.rows:
        assert row["Avg intent score"] >= 80


def test_buying_committee_scores_seniority_correctly(conn):
    accounts = [a.id for a in conn.sfdc.list_accounts()[:5]]
    table = buying_committee(conn, accounts)
    scores = [r["Fit score"] for r in table.rows]
    assert scores == sorted(scores, reverse=True)
    # A CISO is C-Level in Security: the maximum 50 + 30.
    cisos = [r for r in table.rows
             if r["Seniority"] == "C-Level" and r["Function"] == "Security"]
    for row in cisos:
        assert row["Fit score"] == 80


def test_pipeline_in_accounts_only_counts_open_deals(conn):
    account_ids = [a.id for a in conn.sfdc.list_accounts()[:12]]
    table = pipeline_in_accounts(conn, account_ids)
    wanted = set(account_ids)
    expected = sum(o.amount_usd for o in conn.sfdc.list_opportunities()
                   if o.account_id in wanted and o.is_open)
    assert sum(r["Open pipeline (USD)"] for r in table.rows) == expected


def test_pipeline_in_accounts_flags_accounts_with_nothing_open(conn):
    accounts = conn.sfdc.list_accounts()
    with_opp = {o.account_id for o in conn.sfdc.list_opportunities()}
    no_opp = [a.id for a in accounts if a.id not in with_opp][:3]
    table = pipeline_in_accounts(conn, no_opp)
    assert all(r["Open opps"] == 0 for r in table.rows)
    assert "3 of 3 accounts have no open opportunity" in " ".join(table.notes)


# --- table rendering ------------------------------------------------------

def test_markdown_has_a_row_per_record_plus_header_and_separator(conn):
    table = coverage_by_region(conn)
    body = [line for line in table.to_markdown().splitlines()
            if line.startswith("|")]
    assert len(body) == len(table.rows) + 2


def test_empty_table_renders_without_crashing(conn):
    table = pipeline_in_accounts(conn, [])
    assert "No rows matched" in table.to_markdown()


def test_closed_won_rate_is_a_sane_proportion(conn):
    from mktg_core.metrics import closed_won_rate
    rate = closed_won_rate(conn)
    assert 0.0 <= rate <= 1.0
    won = sum(1 for o in conn.sfdc.list_opportunities()
              if o.stage == OppStage.CLOSED_WON)
    assert (rate > 0) == (won > 0)
