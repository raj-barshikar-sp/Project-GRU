from agents.session_memory import detect_account_in_text
from models.routing_decision import is_mail_follow_up
from models.synthesis_output import strip_email_signoff
from agents.orchestrator.workflow import (
    _mail_follow_up_reply,
    _quote_status_mail_reply,
    _remember_scope,
)
from ui.briefing import parse_reply


def test_strip_email_signoff_drops_name_and_role() -> None:
    body = (
        "Hi Helen,\n\n"
        "Following up on the Dayton sandbox.\n\n"
        "Best regards,\n"
        "Jordan Patel\n"
        "Account Executive\n"
    )
    cleaned = strip_email_signoff(body)
    assert cleaned.rstrip().endswith("Best regards,")
    assert "Jordan Patel" not in cleaned
    assert "Account Executive" not in cleaned


def test_acme_quote_mail_has_no_signature_block() -> None:
    assert is_mail_follow_up("create an email artifact for Acme Corp")
    reply = _quote_status_mail_reply(
        {},
        "create an email artifact for Acme Corp",
        "Acme Corp",
    )
    assert "Q-241" in reply
    assert "Hi Helen," in reply
    assert "$640,000" in reply
    assert "Best regards," in reply
    assert "Jordan Patel" not in reply
    assert "Account Executive" not in reply
    assert reply.rstrip().endswith("```")
    email = reply.split("```")[1]
    assert email.strip().endswith("Best regards,")


def test_same_follow_up_after_central_verbal_is_not_quote_mail() -> None:
    query = "create an email artifact for the same"
    reply = _mail_follow_up_reply(
        {},
        query,
        last_territory="central",
        last_agent="revops_forecast",
        last_topic="verbal",
    )
    assert reply
    assert "Q-570" not in reply
    assert "verbal call" in reply.lower()
    assert "2026-Q3-W09" in reply
    assert "Acme Corp" in reply
    assert "Central" in reply or "central" in reply.lower()
    assert "Best regards," in reply
    payload = parse_reply(reply)
    assert payload["artifacts"]
    assert payload["artifacts"][0]["kind"] == "email"
    assert payload["artifacts"][0]["body"].strip().endswith("Best regards,")


def test_create_an_email_does_not_resolve_to_meridian() -> None:
    assert detect_account_in_text("create an email artifact for the same") is None
    assert detect_account_in_text("email for Acme") == "Acme Corp"


def test_quote_mail_skipped_on_forecast_follow_up() -> None:
    reply = _quote_status_mail_reply(
        {},
        "create an email artifact for the same",
        last_agent="revops_forecast",
        last_topic="verbal",
        last_territory="central",
    )
    assert reply == ""


def test_geo_turn_does_not_steal_last_account_from_payload() -> None:
    state: dict[str, str] = {}
    _remember_scope(
        state,
        "Pull the weekly verbal call in Rev Intel for central",
        {"accounts": ["Acme Corp", "Meridian Health"], "records": {"Opportunity": []}},
    )
    assert state.get("last_territory") == "central"
    assert not state.get("last_account")
    assert state.get("last_scope") == "territory"


def test_parse_reply_stores_fenced_email() -> None:
    text = (
        "Here is a paste-ready note.\n\n"
        "```\n"
        "Subject: Central verbal call\n\n"
        "Hi Jordan,\n\n"
        "Please confirm the ACV gap.\n\n"
        "Best regards,\n"
        "```\n"
    )
    payload = parse_reply(text)
    assert payload["kind"] == "plain"
    assert payload["artifacts"][0]["kind"] == "email"
    assert payload["artifacts"][0]["title"] == "Central verbal call"
    assert "Best regards," in payload["artifacts"][0]["body"]
