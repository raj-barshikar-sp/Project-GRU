"""Workspace UI briefing parser, progress labels, and FastAPI routes."""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path

from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from starlette.testclient import TestClient

from mktg_core.contracts.marketing_ops import UPLOADED_LEAD_FILES_STATE
from ui.app import APP_NAME, USER_ID, create_app
from ui.attachments import DecodedAttachment, uploaded_csv_rows
from ui.briefing import parse_reply
from ui.catalog import (
    FilterSelection,
    WRITE_GUARD_REPLY,
    compose_task_message,
    filter_notes,
    write_guard_reply,
)
from ui.chats import ChatStore
from ui.collections import CollectionStore
from ui.progress import THINKING_LABEL, status_for_author
from ui.trace import RunTrace, tracing_enabled

PLAIN_REPLY = "EMEA coverage is 1.46x against a 2.0x target."

BRIEFING = """## Summary
EMEA is the coverage gap this week.

## Key Insights
- EMEA sits at 1.46x versus a 2.0x target.
- Paid Social is the expensive channel.

## Recommended Actions
1. Move budget toward the Zero Trust webinar (owner: analysis, when: this week)
paste: Shift $40k from Paid Social to the webinar.

## Artifacts
### Follow-up note
```
EMEA coverage is 1.46x. Recommend a budget shift.
```
"""


def test_uploaded_csv_rows_are_available_to_deterministic_tools() -> None:
    files = [
        DecodedAttachment(
            filename="leads.csv",
            mime_type="text/csv",
            data=(
                b"First Name,Last Name,Email,Company,Country\n"
                b"Ada,Lovelace,ada@example.com,Vantage,DE\n"
            ),
        )
    ]
    rows = uploaded_csv_rows(files)
    assert rows["leads.csv"][0]["Email"] == "ada@example.com"


def _event(author: str, text: str) -> Event:
    return Event(
        invocation_id="inv",
        author=author,
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=text)]
        ),
    )


class FakeRunner:
    def __init__(self, events: list[Event]) -> None:
        self.events = events
        self.calls = 0
        self.messages: list[str] = []
        self.run_config = None

    async def run_async(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        self.run_config = kwargs.get("run_config")
        content = kwargs.get("new_message")
        if content and content.parts:
            self.messages.append(
                "\n".join(part.text or "" for part in content.parts)
            )
        for event in self.events:
            yield event


def test_parse_reply_keeps_plain_answers() -> None:
    assert parse_reply(PLAIN_REPLY) == {"kind": "plain", "text": PLAIN_REPLY}


def test_a_mocked_write_carries_a_notice_even_when_the_prose_sounds_real() -> None:
    """The model often says 'successfully created' and drops MOCK from the copy.

    The id still contains 701MOCK, which is enough to put a banner on the reply
    so the user is not left believing Salesforce was written to.
    """
    from ui.briefing import MOCK_NOTICE

    paraphrased = (
        "The Salesforce campaign record EMEA-FieldEvent-2026Q3-Zero-Trust "
        "(ID: 701MOCK3637) has been successfully created."
    )
    parsed = parse_reply(paraphrased)
    assert parsed["kind"] == "receipt"
    assert parsed["notice"] == MOCK_NOTICE
    assert any(field["value"] == "701MOCK3637" for field in parsed["fields"])
    labels = {field["label"]: field["value"] for field in parsed["fields"]}
    assert labels.get("Name", "").startswith("EMEA-FieldEvent")
    assert labels.get("Region") == "EMEA"
    assert "notice" not in parse_reply(PLAIN_REPLY)

    client = _client([])
    script = client.get("/static/app.js").text
    assert "function renderBriefing(payload, options = {})" in script
    assert "function renderMarkdown(text)" in script


def test_typed_replies_parse_receipt_question_cannot_and_split_artifacts() -> None:
    receipt = parse_reply(
        "## Receipt\n"
        "Status: Would create. Nothing was written to a live org.\n"
        "Id: 701MOCK0001\n"
        "Name: EMEA-FieldEvent-2026Q3-Zero-Trust\n"
        "Type: Field Event\n"
        "Region: EMEA\n\n"
        "## Assumptions\n"
        "- Type: Field Event\n\n"
        "## Next step\n"
        "Confirm the budget before repeating this."
    )
    assert receipt["kind"] == "receipt"
    assert receipt["notice"]
    assert {field["label"]: field["value"] for field in receipt["fields"]}["Id"] == (
        "701MOCK0001"
    )
    assert receipt["next_step"].startswith("Confirm the budget")

    sixsense = parse_reply(
        "## Receipt\n"
        "Status: Would create. Nothing was written to a live org.\n"
        "- Segment id: SEG-MOCK-03908\n"
        "Name: EMEA-Tradeshow-2026Q3-Key-Accounts\n\n"
        "## Next step\n"
        "Deploy this segment into Marketo as a smart list."
    )
    assert sixsense["kind"] == "receipt"
    assert {field["label"]: field["value"] for field in sixsense["fields"]}["Id"] == (
        "SEG-MOCK-03908"
    )

    tool_receipt = parse_reply(
        "## Receipt\n"
        "Status: Would create. Nothing was written to a real Salesforce org. "
        "This is a mock.\n"
        "Id: 701MOCK1234\n"
        "Name: EMEA-Webinar-2026Q4-Zero-Trust\n"
        "Type: Webinar\n"
        "Region: EMEA\n"
        "Dates: 2026-10-01 to 2026-12-15\n"
        "Budget: 25000 USD\n\n"
        "## Assumptions\n"
        "- Type: Webinar\n"
        "- Region: EMEA"
    )
    assert tool_receipt["kind"] == "receipt"
    fields = {item["label"]: item["value"] for item in tool_receipt["fields"]}
    assert fields["Name"] == "EMEA-Webinar-2026Q4-Zero-Trust"
    assert fields["Budget"] == "25000 USD"
    assert fields["Dates"] == "2026-10-01 to 2026-12-15"

    question = parse_reply(
        "## Question\n"
        "The campaign budget in USD.\n"
        "The Salesforce record needs a budget.\n"
        "Then I will create the mocked campaign."
    )
    assert question["kind"] == "question"
    assert "budget" in question["text"].lower()

    cannot = parse_reply(
        "Updating existing campaign records is not supported automatically.\n\n"
        "Please update the budget in Salesforce."
    )
    assert cannot["kind"] == "cannot"

    two = parse_reply(
        "## Summary\nTwo packs.\n\n"
        "## Artifacts\n"
        "### Email\n```\nhello\n```\n\n"
        "### Spec\n```\nworld\n```"
    )
    assert [item["title"] for item in two["artifacts"]] == ["Email", "Spec"]
    drifted = parse_reply("## Summary\nGo.\n\n## Insights\n- A number.\n")
    assert drifted["kind"] == "briefing"
    assert drifted["insights"] == ["A number."]


def test_parse_reply_builds_briefing() -> None:
    parsed = parse_reply(BRIEFING)
    assert parsed["kind"] == "briefing"
    assert parsed["summary"] == "EMEA is the coverage gap this week."
    assert parsed["insights"][0].startswith("EMEA sits")
    assert parsed["actions"][0] == {
        "action": "Move budget toward the Zero Trust webinar",
        "owner": "analysis",
        "due": "this week",
        "paste": "Shift $40k from Paid Social to the webinar.",
    }
    assert parsed["artifacts"] == [
        {
            "title": "Follow-up note",
            "body": "EMEA coverage is 1.46x. Recommend a budget shift.",
        }
    ]


def test_parse_reply_opens_a_saved_content_file(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "content"
    folder.mkdir()
    (folder / "zero_trust_juniper_capital_brochure.json.md").write_text(
        "# Zero Trust Anchor Asset Brochure - Juniper Capital\n\nBody copy.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.briefing.OUTPUT_DIR", tmp_path)
    parsed = parse_reply(
        "## Summary\nWrote the brochure.\n\n"
        "## Artifacts\n"
        "### Zero Trust Anchor Asset Brochure - Juniper Capital\n"
        "```\n"
        "Saved to output/content/zero_trust_juniper_capital_brochure.json.md\n"
        "```\n"
    )
    assert parsed["kind"] == "briefing"
    assert "Body copy" in parsed["artifacts"][0]["body"]
    assert "Saved to" not in parsed["artifacts"][0]["body"]


def test_chat_script_offers_a_pptx_download_chip() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function renderDeckDownloads(" in script
    assert "payload.downloads" in script
    assert 'kind === "pptx"' in script
    assert 'link.textContent = "Open PowerPoint"' in script
    chat = client.get("/chat").text
    assert "/static/app.js?v=" in chat


def test_parse_reply_attaches_a_pptx_download_without_inlining() -> None:
    parsed = parse_reply(
        "The pipeline review is ready. Deck saved to output/decks/pipeline-review.pptx "
        "with 6 slides (including the title slide)."
    )
    assert parsed["kind"] == "briefing"
    assert "output/decks" not in parsed["summary"]
    assert parsed["downloads"] == [
        {
            "title": "pipeline-review.pptx",
            "url": "/api/decks/pipeline-review.pptx",
            "filename": "pipeline-review.pptx",
        }
    ]
    assert parsed["artifacts"][0]["kind"] == "pptx"
    assert parsed["artifacts"][0]["url"] == "/api/decks/pipeline-review.pptx"


def test_parse_reply_finds_a_backticked_pptx_path() -> None:
    parsed = parse_reply(
        "The PowerPoint presentation has been generated and saved to "
        "`output/decks/campaign-brief-paid-social-cloud-security.pptx`."
    )
    assert parsed["kind"] == "briefing"
    assert parsed["downloads"][0]["url"] == (
        "/api/decks/campaign-brief-paid-social-cloud-security.pptx"
    )
    assert parsed["artifacts"][0]["kind"] == "pptx"


def test_a_pptx_reply_with_bold_summary_uses_briefing_cards() -> None:
    parsed = parse_reply(
        "The PowerPoint slide deck for the Paid Social campaign has been "
        "generated and saved to `output/decks/campaign-brief.pptx`.\n\n"
        "**Summary**\n"
        "It details the campaign goals, target audience, key messaging, "
        "$86,000 budget allocation, and required creative dependencies "
        "across six presentation slides.\n\n"
        "**Artifacts**\n"
    )
    assert parsed["kind"] == "briefing"
    assert "output/decks" not in parsed["summary"]
    assert "86,000" in parsed["summary"]
    assert parsed["artifacts"][0]["kind"] == "pptx"
    assert parsed["artifacts"][0]["url"] == "/api/decks/campaign-brief.pptx"


def test_parse_reply_does_not_read_pptx_bytes_as_markdown(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "decks"
    folder.mkdir()
    (folder / "pipeline-review.pptx").write_bytes(b"PK\x03\x04not-text")
    monkeypatch.setattr("ui.briefing.OUTPUT_DIR", tmp_path)
    parsed = parse_reply(
        "## Summary\nWrote the deck.\n\n"
        "## Artifacts\n"
        "### Pipeline review\n"
        "```\n"
        "Deck saved to output/decks/pipeline-review.pptx\n"
        "```\n"
    )
    assert parsed["kind"] == "briefing"
    assert "PK" not in (parsed["artifacts"][0].get("body") or "")
    assert parsed["artifacts"][0]["kind"] == "pptx"
    assert parsed["artifacts"][0]["url"] == "/api/decks/pipeline-review.pptx"
    assert parsed["downloads"][0]["url"] == "/api/decks/pipeline-review.pptx"


def test_deck_download_rejects_path_traversal() -> None:
    client = TestClient(create_app())
    assert client.get("/api/decks/not-a-pptx.txt").status_code == 400
    sneaky = client.get("/api/decks/%2e%2e%2fsecrets.pptx")
    assert sneaky.status_code in {400, 404}
    assert client.get("/api/decks/missing.pptx").status_code == 404


def test_deck_download_serves_a_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("mktg_core.rendering.deck.OUTPUT_DIR", tmp_path)
    (tmp_path / "pipeline-review.pptx").write_bytes(b"PK\x03\x04deck")
    client = TestClient(create_app())
    response = client.get("/api/decks/pipeline-review.pptx")
    assert response.status_code == 200
    assert response.content == b"PK\x03\x04deck"


def test_generated_content_files_join_the_content_list(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "content"
    folder.mkdir()
    (folder / "zero_trust_juniper_capital_brochure.md").write_text(
        "# Zero Trust Anchor Asset Brochure - Juniper Capital\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ui.catalog.OUTPUT_DIR", tmp_path)
    from ui.catalog import workspace_catalog

    labels = [item["label"] for item in workspace_catalog()["filters"]["content"]]
    assert "Zero Trust Anchor Asset Brochure - Juniper Capital" in labels


def test_parse_reply_keeps_non_briefing_headings_plain() -> None:
    """The stream wrapper only structures its canonical briefing contract."""
    reply = (
        "## Summary\nMunich is the pick.\n\n"
        "## Why Munich\n- 10 unworked accounts.\n\n"
        "## Draft Invite\nJoin us in Munich."
    )
    parsed = parse_reply(reply)
    assert parsed == {"kind": "plain", "text": reply}


def test_parse_reply_ignores_headings_inside_a_fenced_block() -> None:
    """A copied artifact can contain '## ', which must not split the reply."""
    reply = "## Summary\nHere is the note.\n\n### Note\n```\n## Not a pane\n```"
    parsed = parse_reply(reply)
    assert parsed["kind"] == "briefing"
    assert "## Not a pane" in parsed["summary"]


def test_parse_reply_drops_a_padded_empty_section() -> None:
    parsed = parse_reply("## Summary\nDone.\n\n## Artifacts\nNone.")
    assert parsed["kind"] == "briefing"
    assert parsed["artifacts"] == []


def test_parse_reply_tolerates_a_missing_space_after_the_hashes() -> None:
    """A slightly malformed '##Summary' should still degrade to a briefing.

    The heading normalisation keeps a specialist's structured answer from
    falling all the way back to plain text over one missing space.
    """
    parsed = parse_reply("##Summary\nSpend is up.\n\n##Key Insights\n- Paid Social leads.")
    assert parsed["kind"] == "briefing"
    assert parsed["summary"] == "Spend is up."
    assert parsed["insights"] == ["Paid Social leads."]


def test_parse_reply_still_excludes_triple_hash_subheadings() -> None:
    """'###' is a pane sub-title, not a top-level heading, even after the

    no-space tolerance above; a '### '-only reply must stay plain.
    """
    reply = "### Note\nJust a sub-heading, no summary pane here."
    assert parse_reply(reply) == {"kind": "plain", "text": reply}


def test_a_briefing_may_omit_the_sections_it_has_nothing_for() -> None:
    """A performance read is told not to recommend, so it has no actions.

    Requiring every section is what made an agent write a heading explaining
    that another specialist handles recommendations.
    """
    parsed = parse_reply(
        "## Summary\nSpend is up 12%.\n\n## Key Insights\n- Paid Social is the outlier."
    )
    assert parsed["kind"] == "briefing"
    assert parsed["insights"] == ["Paid Social is the outlier."]
    assert parsed["actions"] == []
    assert parsed["artifacts"] == []


def test_placeholder_owner_and_timing_are_dropped() -> None:
    """"owner: N/A · when: N/A" is the model filling in the format, not data."""
    parsed = parse_reply(
        "## Summary\nDone.\n\n## Recommended Actions\n1. Review the funnel (owner: N/A, when: N/A)"
    )
    action = parsed["actions"][0]
    assert action["action"] == "Review the funnel"
    assert action["owner"] == ""
    assert action["due"] == ""


def test_custom_headings_are_not_mistaken_for_a_briefing() -> None:
    """Only the canonical set renders as a briefing; anything else stays plain."""
    reply = "## Summary\nMunich.\n\n## Why Munich\n- 10 accounts."
    assert parse_reply(reply) == {"kind": "plain", "text": reply}


def test_marketing_requests_pass_the_scope_gate() -> None:
    from ui.scope import is_in_scope

    assert is_in_scope("How is our pipeline looking?")
    # Off-topic chat is refused locally without a model call.
    assert not is_in_scope("What movie should I watch tonight?")


def test_a_ticked_filter_makes_a_bare_request_in_scope() -> None:
    """The selected campaign/account is the subject even when the text is thin."""
    from ui.scope import is_in_scope

    assert not is_in_scope("tell me more about it")
    assert is_in_scope("tell me more about it", has_filters=True)


def test_a_short_follow_up_stays_in_scope_only_after_an_in_scope_turn() -> None:
    from ui.scope import is_in_scope

    # No marketing vocabulary of its own, so it only rides on the prior turn.
    assert is_in_scope("what about the other one?", previous_turn_in_scope=True)
    assert not is_in_scope("what about the other one?", previous_turn_in_scope=False)


def test_small_talk_gets_a_canned_reply_but_marketing_wins_a_tie() -> None:
    from ui.scope import GREETING_REPLY, THANKS_REPLY, social_reply

    assert social_reply("Hello, James!") == GREETING_REPLY
    assert social_reply("thanks") == THANKS_REPLY
    # A greeting bolted onto real work is not small talk.
    assert social_reply("hi, how is our pipeline looking?") is None


def test_status_names_specialists_and_hides_unknown_authors() -> None:
    """The root router carries the generic line, not a team hand-off.

    It speaks before it has chosen anything, so "Handing this to analysis…"
    would be a lie; it used to be silent instead, which left the status line
    on the client's placeholder until the first specialist replied.
    """
    assert status_for_author("analysis_pipeline_health") == "Checking pipeline coverage…"
    assert status_for_author("campaign_brief_deck") == "Building the campaign PowerPoint…"
    assert status_for_author("marketing_orchestrator") == THINKING_LABEL
    assert status_for_author("secret_debug") is None


def _store() -> ChatStore:
    return ChatStore(Path(tempfile.mkdtemp()) / "chats")


def _folders() -> CollectionStore:
    return CollectionStore(Path(tempfile.mkdtemp()) / "collections")


def _client(
    events: list[Event],
    chat_store: ChatStore | None = None,
    collection_store: CollectionStore | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            runner=FakeRunner(events),
            session_service=InMemorySessionService(),
            chat_store=chat_store or _store(),
            collection_store=collection_store or _folders(),
        )
    )


def _seed_chat(store: ChatStore, chat_id: str, title: str, user: str = "How is our pipeline looking?") -> None:
    store.append_user(
        chat_id=chat_id,
        session_id="sess",
        title=title,
        user=user,
        tags=[],
        filters={},
    )


def _sse_events(response_text: str) -> list[dict]:
    payloads = []
    for block in response_text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[5:].strip()))
    return payloads


def test_the_page_shell_is_never_served_from_cache() -> None:
    """A cached shell keeps requesting the previous build's CSS and JS."""
    client = _client([])
    home = client.get("/")
    assert home.headers["cache-control"] == "no-store"
    # Both assets are pinned to the same build, so one cannot go stale alone.
    body = home.text
    versions = set(re.findall(r"/static/(?:app\.js|styles\.css)\?v=(\d+)", body))
    assert len(versions) == 1, versions


def test_landing_links_to_workspace() -> None:
    client = _client([])
    home = client.get("/")
    assert home.status_code == 200
    assert b"Get started" in home.content
    assert b'id="landing"' in home.content
    assert b">James</h1>" in home.content
    assert b"James the Marketing Minion" not in home.content
    assert b'href="/dashboard"' in home.content
    assert b'setAttribute("href", "/chat")' not in home.content
    assert b"/static/james.png" in home.content
    assert b"/dashboard" in home.content
    assert b"send Bob a task" not in home.content
    workspace = client.get("/chat")
    assert workspace.status_code == 200
    assert b'id="task-menu"' in workspace.content
    assert b'id="task-items"' in workspace.content
    assert b'id="chat-history"' in workspace.content
    assert b'id="new-chat"' in workspace.content
    assert b'id="collection-prompt-dialog"' in workspace.content
    assert b'id="move-collection-dialog"' in workspace.content
    assert b'id="selected-chips"' in workspace.content
    assert b'id="nav-artifacts"' in workspace.content
    assert b'id="artifact-library"' in workspace.content
    assert b'id="artifact-pane"' in workspace.content
    assert b'id="artifact-pane-copy"' in workspace.content
    assert b'id="artifact-mode-preview"' in workspace.content
    assert b'id="artifact-mode-source"' in workspace.content
    assert b'id="artifact-resize"' in workspace.content
    assert b'id="artifact-pane-expand"' in workspace.content
    assert b"artifact-icon-expand" in workspace.content
    assert b"artifact-icon-collapse" in workspace.content
    assert b"Task menu" in workspace.content
    assert b'id="chat-content"' in workspace.content
    assert b'id="scroll-bottom"' in workspace.content
    assert b'id="composer-drop"' in workspace.content
    assert b"data-theme-toggle" in workspace.content
    assert b'id="filters-dialog"' in workspace.content
    assert b'id="filter-campaign-types"' in workspace.content
    assert b">List of Campaigns</h3>" in workspace.content
    assert b">Campaign Types</h3>" in workspace.content
    assert b">List of Asset Types</h3>" in workspace.content
    assert b">List of Content</h3>" in workspace.content
    assert b'id="filter-content"' in workspace.content
    assert b"Opp size" not in workspace.content
    assert b"Rep opps" not in workspace.content
    assert b"Geo / GVP / AVP / Boats" not in workspace.content
    assert b'id="filter-campaigns"' in workspace.content
    assert b'id="filter-asset-types"' in workspace.content
    assert b'id="open-tasks"' in workspace.content
    assert b'id="open-tasks-empty"' in workspace.content
    assert b'id="open-filters-empty"' in workspace.content
    assert b"Choose a task" in workspace.content
    assert b"Set filters" in workspace.content
    assert b"Open task menu" not in workspace.content
    assert b'id="open-filters"' in workspace.content
    assert b'id="sidebar-selected"' in workspace.content
    assert b"Filters" in workspace.content
    assert b'id="starters"' not in workspace.content
    assert b'id="open-accounts"' not in workspace.content
    script = client.get("/static/app.js").text
    assert "function openTaskMenu(anchor)" in script
    assert "showTaskGroup(group, button)" in script
    assert 'el("p", "task-menu-subhead", section)' in script
    assert "function persistChats" in script
    assert "function restoreActiveChat" in script
    assert "function deleteChat" in script
    assert "function renderQueryNav" in script
    assert "function currentFilters()" in script
    assert 'campaigns: selectedValues("campaign")' in script
    assert 'campaign_types: selectedValues("campaign_type")' in script
    assert client.get("/chat").status_code == 200


def test_sailpoint_brand_tokens_and_landing_doors() -> None:
    client = _client([])
    sheet = client.get("/static/styles.css").text
    assert "--cobalt: #0033a1;" in sheet
    assert "--blue: #0071ce;" in sheet
    assert "--fg: #111111;" in sheet
    assert "--page: #ffffff;" in sheet
    assert "--page: #0a0c10;" in sheet
    assert "--fg-muted: #415364;" in sheet
    assert "--page: #415364;" not in sheet
    assert "--orchid: #e17fd2;" in sheet
    assert "--sail:" in sheet
    assert "#1a5cff" not in sheet

    from ui.scope import GREETING_REPLY, CAPABILITY_REPLY

    home = client.get("/").text
    assert 'href="/dashboard"' in home
    assert 'class="landing-cap-grid t-avatar-group"' in home
    assert "Marketing jobs in one place" in home
    assert "minion" not in GREETING_REPLY.lower()
    assert "minion" not in CAPABILITY_REPLY.lower()

    workspace = client.get("/chat").text
    assert 'href="/dashboard"' in workspace
    assert 'id="toggle-sidebar"' in workspace
    assert 'class="workspace-bar"' in workspace

    script = client.get("/static/theme.js").text
    assert "data-theme-toggle" in script
    chat = client.get("/chat").text
    versions = set(re.findall(r"/static/(?:app\.js|styles\.css)\?v=(\d+)", chat))
    assert len(versions) == 1, versions


def test_transitions_dev_hooks_are_served() -> None:
    client = _client([])
    sheet = client.get("/static/transitions.css").text
    assert "--duration-quick:" in sheet
    assert "@media (prefers-reduced-motion: reduce)" in sheet
    assert ".t-dropdown" in sheet
    assert ".t-stream-w" in sheet
    assert ".t-think-text" in sheet
    assert "@view-transition" in sheet
    assert ".t-panel" in sheet
    assert "scale(var(--scale-large))" in sheet
    assert "james-bar" not in sheet

    home = client.get("/").text
    assert "/static/transitions.css" in home
    assert "t-stagger" in home
    assert "t-acc" in home
    assert "t-avatar-group" in home
    assert "/static/transitions.js" in home

    chat = client.get("/chat").text
    assert 'class="app-dialog app-popover t-dropdown"' in chat
    assert "t-modal" in chat
    assert 'id="app-toast"' in chat
    assert 'id="send-swap"' in chat
    assert "JamesMotion" in client.get("/static/app.js").text
    assert "dismissPlaceholder" in client.get("/static/app.js").text
    assert "is-hiding" in client.get("/static/app.js").text
    theme = client.get("/static/theme.js").text
    assert "startViewTransition" in theme
    assert 'types: ["theme"]' in theme
    assert "t-panel" in chat
    assert "is-closing" in client.get("/static/artifacts.js").text

    dash = client.get("/dashboard").text
    assert 'id="dash-skel"' in dash
    assert "t-tabs-pill" in dash
    assert "t-digit-group" in client.get("/static/dashboard.js").text
    assert "t-text-swap" in dash
    assert "#1a1a1a" not in client.get("/static/styles.css").text
    assert "sidebar-inner" in chat
    assert "t-page-enter" in sheet
    assert "crossFade" in client.get("/static/transitions.js").text
    assert "function syncChatUrl()" in client.get("/static/app.js").text
    assert "function syncDashUrl()" in client.get("/static/dashboard.js").text
    assert 'id="composer-hint"' in chat
    assert 'id="composer-suggest"' in chat
    assert 'id="artifact-pane-version-btn"' in chat
    assert "send: false" in client.get("/static/dashboard.js").text
    assert "gru-chats" in client.get("/static/app.js").text
    assert 'setAttribute("href", "/chat")' not in home
    assert 'addEventListener("james-theme"' in client.get("/static/dashboard.js").text
    assert "t-theme-fade-in" in sheet
    assert "--theme-wipe-dur" in sheet
    assert "view-transition-name: theme-toggle" in sheet
    assert "chartColors" in client.get("/static/dashboard.js").text
    assert '["#3dd6ff", "#c8ff45", "#ff5ec8"' in client.get("/static/dashboard.js").text
    assert ".artifact-pane-preview.is-code" in client.get("/static/styles.css").text
    assert "background: #1e1e1e" not in client.get("/static/styles.css").text
    assert "revealRows" in client.get("/static/transitions.js").text
    assert "enterSeen" in client.get("/static/transitions.js").text
    assert ".t-row" in sheet
    assert ".collection-fold" in sheet
    assert "overflow: hidden" in client.get("/static/transitions.css").text.split(".collection-fold {", 1)[1].split("}", 1)[0]
    assert ".history-block:not(.is-open) .collection-fold-inner" not in client.get("/static/transitions.css").text
    assert ".history-block.is-collapsed .collection-fold-inner" in client.get("/static/transitions.css").text
    assert ".dash-chart-hit.t-bar" in sheet
    assert "t-stagger-line--3" in chat
    assert ".placeholder-actions.t-stagger-line" in sheet
    assert "t-banner" in chat
    assert "growNode" in client.get("/static/dashboard.js").text
    assert "collection-chevron" not in client.get("/static/app.js").text
    assert ".collection-toggle::after" in sheet
    assert ".dash-donut-slices.is-in" not in sheet
    assert "t-donut-in" not in sheet
    assert ".dash-donut-slices" in sheet
    assert "sweep >= Math.PI * 1.999" in client.get("/static/dashboard.js").text
    assert "THINK_STATES" not in client.get("/static/transitions.js").text
    assert "Reading the book" not in client.get("/static/app.js").text
    assert "function settleFirstQuery(" in client.get("/static/app.js").text
    assert ".shell.is-empty:not(.is-library-view) .composer-card" in client.get("/static/styles.css").text


def test_sending_a_message_keeps_the_filters_but_releases_the_task() -> None:
    """The client sends the composed draft plus current filter ticks."""
    client = _client([])
    script = client.get("/static/app.js").text
    send_path = script.split("async function askJames")[1].split("async function ")[0]
    assert "const body = { session_id: sessionId, message: text, filters, chat_id: chatId };" in send_path
    assert "task_id:" not in send_path.split("fetch(")[0]
    assert "clearAttachments()" in send_path
    assert "function currentFilters()" in script
    assert 'id="clear-selections"' in client.get("/chat").text
    assert "function clearTaskSelection()" in script
    assert "async function startNewChat(" in script
    assert "function dashboardLaunchParams()" in script
    assert "const launching = dashboardLaunchParams();" in script
    assert "if (launching || !restoreActiveChat()) showEmptyCanvas();" in script


def test_a_reload_lands_on_the_chat_it_left() -> None:
    """Boot restores the saved thread before it waits on the network.

    The thread is in localStorage, so painting it after /api/chats and
    /api/workspace only buys a flash of the empty canvas on every reload.
    """
    client = _client([])
    script = client.get("/static/app.js").text
    boot = script.split("async function boot()")[1]
    restore = boot.index("if (launching || !restoreActiveChat()) showEmptyCanvas();")
    assert restore < boot.index("await loadLibrary();")
    assert restore < boot.index('fetch("/api/workspace")')
    # syncChatUrl writes the task and filter ticks back into the address bar,
    # so a reload carries launch params for the chat that is already open.
    assert "function returningToChat()" in script
    launch = script.split("function dashboardLaunchParams()")[1].split("function applyDashboardLaunch")[0]
    assert "if (returningToChat()) return false;" in launch
    assert 'entry?.type === "reload"' in script
    # A new chat is a place too: reloading one stays on the empty canvas
    # rather than dropping the user into the newest thread.
    load = script.split("function loadChats()")[1].split("function syncBusy")[0]
    assert 'const savedId = raw.activeChatId || "";' in load
    assert "chats[0]?.id" not in load


def test_empty_composer_and_chat_switch_clear_task_and_filters() -> None:
    """Task chips and filter ticks reset when the box is emptied or the chat changes."""
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function clearAllSelections()" in script
    assert "function hasSelections()" in script
    open_path = script.split("function openChat(chatId)")[1].split("window.JamesChat")[0]
    assert "clearAllSelections();" in open_path
    assert "prompt.value = \"\";" in open_path
    assert "settleIncompleteTurn();" not in open_path
    assert "resumePendingChat(chat.id)" in open_path
    assert "detachInFlight();" in open_path
    new_path = script.split("async function startNewChat(")[1].split("function renderQueryNav()")[0]
    assert "!hasSelections()" in new_path
    assert "clearAllSelections();" in new_path
    assert "keepDraft" in new_path
    delete_path = script.split("async function deleteChat(chatId)")[1].split("function ensureActiveChat")[0]
    assert "clearAllSelections();" in delete_path
    assert 'if (!prompt.value.trim() && hasSelections()) clearAllSelections();' in script
    clear_listener = script.split('getElementById("clear-selections")')[1].split("boot();")[0]
    assert "clearAllSelections();" in clear_listener


def test_composer_suggests_a_new_chat_when_the_task_changes() -> None:
    """Used threads prompt a new chat on an unrelated task, not on the next job."""
    client = _client([])
    chat = client.get("/chat").text
    assert 'id="composer-suggest"' in chat
    assert 'id="composer-suggest-primary"' in chat
    assert "Pick a task, edit if you want, then send." in chat
    assert "Ask James" in chat
    assert "Let’s get some work done!" in chat
    assert "Choose a task" in chat
    assert "Set filters" in chat
    assert "Type below, or choose a task and set filters." in chat
    assert "/static/assets/sailpoint-logo.png" in chat
    assert "/static/assets/sailpoint-logo-inverse.png" in chat
    assert 'id="open-tasks-empty"' in chat
    assert 'id="open-filters-empty"' in chat
    assert 'class="shell is-empty"' in chat
    assert 'class="app-dialog-field"' in chat

    script = client.get("/static/app.js").text
    assert "function shouldSuggestNewChat(nextTaskId)" in script
    assert "function spokenLine(summary)" in script
    assert "LAST_JOB_KEY = \"gru-last-job\"" in script
    assert "Want this next?" in script
    assert "class=\"briefing-voice\"" in script or 'el("p", "briefing-voice"' in script
    assert "findTask(sentTaskId)?.next_task === nextTaskId" in script
    assert "function offerTaskSwitch(nextTaskId)" in script
    assert "function offerFilterRefresh()" in script
    assert "keepDraft: true" in script
    assert "Start new chat" in script
    assert "Stay here" in script
    select_path = script.split("function selectTask(taskId)")[1].split("function renderAttachChips()")[0]
    assert "shouldSuggestNewChat(taskId)" in select_path
    assert "offerTaskSwitch(taskId)" in select_path
    send_path = script.split("async function askJames")[1].split("async function ")[0]
    assert "hideComposerSuggest()" in send_path
    assert "sentTaskId = activeTask || sentTaskId" in send_path

    sheet = client.get("/static/styles.css").text
    assert ".composer-suggest" in sheet
    assert ".composer-suggest[hidden]" in sheet


def test_selected_filters_show_as_removable_tags_on_the_composer() -> None:
    client = _client([])
    home = client.get("/chat").text
    assert 'id="selected-chips"' in home
    assert 'id="sidebar-selected"' in home

    script = client.get("/static/app.js").text
    assert "function renderSelection()" in script
    assert "function makeSelectionChip(label, onClear)" in script
    assert "selection-chip-x" in script

    sheet = client.get("/static/styles.css").text
    assert ".selection-chip" in sheet or ".selected-chips" in sheet


def test_hidden_attribute_is_not_overridden_by_layout_rules() -> None:
    client = _client([])
    home = client.get("/chat").text
    assert 'id="send-swap"' in home
    assert 'id="stop"' in home
    assert 'id="composer-drop-overlay"' in home

    sheet = client.get("/static/styles.css").text
    # `.icon-btn { display: grid }` outranks the user agent's `[hidden]` rule,
    # so overlays and popovers still need the important hide.
    assert "[hidden] {\n  display: none !important;\n}" in sheet


def test_status_shows_the_thinking_minion_with_a_still_fallback() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    sheet = client.get("/static/styles.css").text
    assert "function setStatus(node, label)" in script
    assert 'node.querySelector(".status-label")' in script
    assert ".status-dots" in sheet
    assert ".status {" in sheet


def test_thinking_panel_streams_model_thoughts() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    sheet = client.get("/static/styles.css").text
    assert "function setReasoningOpen" in script
    assert 'event.type === "reasoning"' in script
    assert 'event.type === "reasoning_done"' in script
    assert ".reasoning-trigger" in sheet
    assert "reasoning-shimmer" in sheet
    thought = Event(
        invocation_id="inv",
        author="marketing_orchestrator",
        content=types.Content(
            role="model",
            parts=[types.Part(text="Checking EMEA coverage first.", thought=True)],
        ),
    )
    runner_client = _client(
        [thought, _event("analysis_pipeline_health", PLAIN_REPLY)]
    )
    created = runner_client.post("/api/session").json()
    with runner_client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How is our pipeline looking?",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    types_seen = [event["type"] for event in events]
    assert "reasoning" in types_seen
    assert types_seen[-2:] == ["reasoning_done", "done"]
    reasoning = next(event for event in events if event["type"] == "reasoning")
    assert reasoning["kind"] == "thought"
    assert "Checking EMEA coverage first." in reasoning["text"]
    streamed = "".join(event["text"] for event in events if event["type"] == "delta")
    assert "Checking EMEA coverage first." not in streamed
    reply = next(event for event in events if event["type"] == "reply")
    assert "Checking EMEA coverage first." not in reply["text"]


def _thought(text: str, *, partial: bool | None = None) -> Event:
    return Event(
        invocation_id="inv",
        author="marketing_orchestrator",
        partial=partial,
        content=types.Content(
            role="model", parts=[types.Part(text=text, thought=True)]
        ),
    )


def test_thinking_arrives_in_pieces_without_repeating_itself() -> None:
    """A streaming run sends each piece, then the whole turn again.

    The panel reads the text it is given, so the repeat has to be folded in
    here rather than shown twice.
    """
    runner = FakeRunner(
        [
            _thought("Checking EMEA ", partial=True),
            _thought("coverage first.", partial=True),
            _thought("Checking EMEA coverage first."),
            _event("analysis_pipeline_health", PLAIN_REPLY),
        ]
    )
    client = TestClient(
        create_app(
            runner=runner,
            session_service=InMemorySessionService(),
            chat_store=_store(),
        )
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How is our pipeline looking?",
        },
    ) as response:
        body = "".join(response.iter_text())
    thinking = [
        event["text"] for event in _sse_events(body) if event["type"] == "reasoning"
    ]
    # Each piece moves the panel on, and the aggregated repeat adds nothing.
    assert thinking == ["Checking EMEA ", "Checking EMEA coverage first."]
    assert runner.run_config is not None
    assert runner.run_config.streaming_mode is StreamingMode.SSE


def test_a_second_turn_of_thinking_starts_its_own_paragraph() -> None:
    runner = FakeRunner(
        [
            _thought("Routing this to analysis."),
            _thought("Now checking the format."),
            _event("analysis_pipeline_health", PLAIN_REPLY),
        ]
    )
    client = TestClient(
        create_app(
            runner=runner,
            session_service=InMemorySessionService(),
            chat_store=_store(),
        )
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How is our pipeline looking?",
        },
    ) as response:
        body = "".join(response.iter_text())
    thinking = [
        event["text"] for event in _sse_events(body) if event["type"] == "reasoning"
    ]
    assert thinking[-1] == "Routing this to analysis.\n\nNow checking the format."


def test_the_thinking_panel_keeps_the_time_it_took() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    sheet = client.get("/static/styles.css").text
    assert "Thought for ${seconds}s" in script
    assert 'reasoning.dataset.done = "true"' in script
    # The panel follows the newest line while the thinking is still arriving.
    assert "reasoningBody.scrollTop = reasoningBody.scrollHeight" in script
    # Once the answer starts, the thoughts fold away until the user opens them.
    assert 'if (reasoning.dataset.streaming === "true") finishReasoning()' in script
    # Settling is one-way, so reopening the panel survives the rest of the run.
    assert 'if (reasoning.dataset.done === "true") return;' in script
    # A chat restored from storage starts folded, except a still-running turn.
    assert 'for (const box of threadEl().querySelectorAll(".turn:not(.pending) .reasoning"))' in script
    assert "setReasoningOpen(box, false);" in script
    # The header stays a button, which is how the thoughts are read afterwards.
    assert '.reasoning-trigger' in sheet
    assert '.reasoning[data-done="true"]:not(.is-open)' in sheet
    assert '.reasoning[data-done="true"]:not(.is-open)' in sheet


def test_stream_wrapper_uses_a_simple_prompt_and_copyable_reply() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function addReplyCopy(parent, text, options = {})" in script
    assert "navigator.clipboard.writeText(button.dataset.copy" in script
    assert "function briefingText(payload)" in script
    assert "function renderBriefing(payload, options = {})" in script
    assert 'event.kind === "briefing"' in script
    assert "function currentFilters()" in script
    assert 'campaigns: selectedValues("campaign")' in script

def test_briefing_renders_fixed_cards_and_copyable_artifacts() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    for heading in ("Summary", "Key insights", "Recommended actions"):
        assert f'"{heading}"' in script
    assert 'addCopy(paste, action.paste, "Copy paste line")' in script
    assert "function persistChatArtifacts" in script
    assert "JamesArtifacts" in script
    assert "function artifactChipIcon" in script
    assert "JamesArtifacts?.kindIcon" in script
    assert "openPane(item, undefined, { instant: true })" in script
    assert 'el("button", "artifact-chip-download", kind === "pptx" ? "Open" : "Download")' in script
    assert "function renderArtifactPreview" in script
    assert "function briefingHeader()" in script
    assert "function selectedCampaign()" in script
    assert 'metrics.push({ label: "Spend", value: `$${spend[1]}` });' in script
    assert 'metrics.push({ label: "MQLs", value: mqls[1] });' in script
    assert 'metrics.push({ label: "Days left", value: days[1] });' in script
    assert "function renderSections" not in script
    sheet = client.get("/static/styles.css").text
    assert ".briefing {" in sheet
    assert ".card {" in sheet
    assert ".briefing-head {" in sheet
    assert ".briefing-pill {" in sheet
    assert ".briefing-title {" in sheet


def test_quote_emails_render_as_copy_cards() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    sheet = client.get("/static/styles.css").text
    assert "function looksLikeEmail" in script
    assert "function fenceEmails" in script
    assert "function artifactBlock" in script
    assert "artifact-${kind" in script
    assert ".md-prose .artifact" in sheet
    assert "var(--paste-bubble)" in sheet
    assert client.get("/favicon.ico").status_code == 200
    assert client.get("/static/assets/mesh.svg").status_code == 200


def test_plain_replies_use_the_stream_wrapper() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert 'streamEl = el("div", "stream t-stream")' in script
    assert "function renderMarkdown" in script
    assert "const applyReply = (event) =>" in script
    sheet = client.get("/static/styles.css").text
    stream = sheet.split(".stream {")[1].split("}")[0]
    assert "white-space: pre-wrap" in stream


def test_a_finished_turn_loses_pending_state_before_the_next_prompt() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert 'const inFlight = last.classList.contains("pending");' in script
    reply_path = script.split('if (event.type === "reply")')[1]
    assert 'turn.classList.remove("pending")' in reply_path


def test_workspace_and_session_endpoints() -> None:
    client = _client([])
    assert client.get("/api/starters").status_code == 404
    workspace = client.get("/api/workspace").json()
    assert workspace["assistant"]["name"] == "James"
    assert workspace["assistant"]["title"] == "James"
    assert workspace["ui"]["reasoning"] is True
    groups = [group["label"] for group in workspace["tasks"]]
    assert groups == [
        "Campaign Design",
        "ABM",
        "Content Generation (Jasper)",
        "Brand",
        "Analysis",
        "Regional Event Marketing",
        "Marketing Operations",
    ]
    assert all(
        group["agent"] in {
            "analysis_orchestrator",
            "events_orchestrator",
            "mops_orchestrator",
            "campaign_design_orchestrator",
            "abm_orchestrator",
            "content_orchestrator",
            "brand_orchestrator",
        }
        for group in workspace["tasks"]
    )
    assert [item["id"] for item in workspace["agents"]] == [
        group["id"] for group in workspace["tasks"]
    ]
    assert any(item["id"].startswith("ACC-") for item in workspace["filters"]["accounts"])
    assert any(item["id"].startswith("CMP-") for item in workspace["filters"]["campaigns"])
    assert all("spend" in item and "health" in item for item in workspace["filters"]["campaigns"])
    assert all("start_date" in item and "end_date" in item for item in workspace["filters"]["campaigns"])
    assert any(item["id"] in {"AMER", "EMEA", "APJ"} for item in workspace["filters"]["geos"])
    assert any(item["id"] == "Webinar" for item in workspace["filters"]["campaign_types"])
    assert any(item["id"] == "Whitepaper" for item in workspace["filters"]["asset_types"])
    assert any(item["id"].startswith("AS-") for item in workspace["filters"]["content"])
    assert "compatibility" not in workspace
    all_tasks = [
        task
        for group in workspace["tasks"]
        for task in group["items"]
    ]
    assert all("filter_policy" in task for task in all_tasks)
    event_task = next(task for task in all_tasks if task["id"] == "attendee_list")
    assert event_task["filter_policy"]["campaign_types"] == [
        "Field Event",
        "Tradeshow",
    ]
    assert event_task["filters"] == ["campaign", "campaign_type"]
    list_load = next(task for task in all_tasks if task["id"] == "list_load")
    assert list_load["filter_policy"]["categories"] == ["events"]
    assert list_load["filters"] == []
    sixsense = next(task for task in all_tasks if task["id"] == "sixsense_segment")
    assert sixsense["filter_policy"]["categories"] == ["campaigns", "accounts"]
    assert sixsense["filters"] == ["campaign"]
    abm_intel = next(task for task in all_tasks if task["id"] == "abm_account_intel")
    assert abm_intel["filters"] == []
    event_location = next(task for task in all_tasks if task["id"] == "event_location")
    assert event_location["filters"] == ["campaign_type"]
    assert "financial services" not in sixsense["default_prompt"].lower()
    assert "surging" not in sixsense["default_prompt"].lower()
    assert "{campaign}" in sixsense["scoped_prompt"]
    assert all(
        "zero trust" not in task["default_prompt"].lower()
        and "munich" not in task["default_prompt"].lower()
        for task in all_tasks
    )
    create_campaign = next(task for task in all_tasks if task["id"] == "create_campaign")
    assert create_campaign["filter_policy"]["categories"] == [
        "campaigns",
        "campaign_types",
        "accounts",
    ]
    assert "Create a webinar" not in create_campaign["default_prompt"]
    assert "{campaign_type}" in create_campaign["scoped_prompt"]
    assert any(item["id"].startswith("EVT-") for item in workspace["filters"]["events"])
    assert any(item["id"].startswith("ACC-") for item in workspace["filters"]["accounts"])
    task_ids = {task["id"] for task in all_tasks}
    assert {
        "campaign_ideation",
        "campaign_brief",
        "campaign_ppt",
        "competitive_messaging",
        "write_content",
        "translate_asset",
        "asset_grid",
        "asset_grid_product_launch",
        "sentiment",
        "share_of_voice",
        "campaign_performance",
        "budget_shift",
        "event_location",
        "create_campaign",
        "sixsense_segment",
        "abm_account_selection",
        "abm_account_intel",
        "abm_multichannel",
    } <= task_ids
    grids = [task for task in all_tasks if task["id"].startswith("asset_grid")]
    assert grids and all(task.get("section") == "Asset grid" for task in grids)
    assert next(task for task in grids if task["id"] == "asset_grid")["label"] == "Build an asset grid"
    brief = next(task for task in all_tasks if task["id"] == "campaign_brief")
    assert brief["next_task"] == "campaign_ppt"
    ppt = next(task for task in all_tasks if task["id"] == "campaign_ppt")
    assert ppt["next_task"] == "write_content"
    assert "Generate a PPT" in ppt["default_prompt"]
    assert workspace["assistant"]["region"] == "EMEA"
    session = client.post("/api/session").json()
    assert session["session_id"]
    assert session["last_account"] == ""


def test_chat_streams_status_then_plain_reply() -> None:
    client = _client(
        [
            _event("analysis_pipeline_health", '{"status":"ok","secret":"do-not-show"}'),
            _event("analysis_pipeline_health", PLAIN_REPLY),
        ]
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How is our pipeline looking?",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    types_seen = [event["type"] for event in events]
    # A thinking line goes out before the run starts, so the wait never shows
    # the client placeholder, then the specialist replaces it.
    assert types_seen[:4] == ["prompt", "status", "status", "delta"]
    assert events[1]["label"] == THINKING_LABEL
    assert events[2]["label"] == "Checking pipeline coverage…"
    streamed = "".join(event["text"] for event in events if event["type"] == "delta")
    assert "1.46x" in streamed
    assert "do-not-show" not in streamed
    reply = next(event for event in events if event["type"] == "reply")
    assert reply["kind"] == "plain"
    assert "1.46x" in reply["text"]
    assert events[-2]["type"] == "reasoning_done"
    assert events[-1]["type"] == "done"


def test_a_briefing_is_not_streamed_as_raw_markdown_first() -> None:
    """The cards are the only render, so no "## Summary" pass precedes them."""
    client = _client([_event("analysis_pipeline_health", BRIEFING)])
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How is our pipeline looking?",
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert not [event for event in events if event["type"] == "delta"]
    reply = next(event for event in events if event["type"] == "reply")
    assert reply["kind"] == "briefing"
    assert reply["insights"]
    # Plain answers have no structure to flash, so they still stream by word.
    plain = _client([_event("analysis_pipeline_health", PLAIN_REPLY)])
    created = plain.post("/api/session").json()
    with plain.stream(
        "POST",
        "/api/chat",
        json={"session_id": created["session_id"], "message": "pipeline coverage?"},
    ) as response:
        body = "".join(response.iter_text())
    assert [event for event in _sse_events(body) if event["type"] == "delta"]


def test_a_briefing_lands_complete_instead_of_being_typed_in() -> None:
    """Structured briefings skip the word stream and land as cards."""
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function renderBriefing(payload, options = {})" in script
    apply = script.split("const applyReply = (event) =>")[1].split("const tickReveal")[0]
    assert "paintReplyNode(" in apply
    assert "autoOpen: true" in apply
    assert "revealLatestQuery(turn)" in apply
    paint = script.split("function paintReplyNode(event, options = {})")[1].split("function paintTurnReply")[0]
    assert 'event.kind === "briefing"' in paint
    assert "renderBriefing(" in paint
    assert "persistChatArtifacts" in paint
    assert "function restoreActiveChat()" in script
    assert "function hydrateTurns()" in script

    sheet = client.get("/static/styles.css").text
    assert ".briefing {" in sheet
    assert ".card.pending" not in sheet


def test_structured_replies_skip_the_plain_text_reveal_queue() -> None:
    script = _client([]).get("/static/app.js").text
    reply_handler = script.split('if (event.type === "reply")')[1].split(
        'if (event.type === "error")'
    )[0]
    assert 'event.kind !== "plain"' in reply_handler
    immediate = reply_handler.split('event.kind !== "plain"')[1].split(
        "pendingReply = event"
    )[0]
    assert "applyReply(event)" in immediate
    assert "return;" in immediate


def test_the_run_trace_is_off_by_default_and_flags_repeated_answers(
    monkeypatch,
) -> None:
    """Evidence for where a 20-30s request goes, before the tree is changed.

    AgentTool returns to its caller, so the layers above the specialist can
    restate the whole artifact on the way back up. Several long emissions in
    one run is what that looks like.
    """
    monkeypatch.delenv("MKTG_TRACE", raising=False)
    assert not tracing_enabled()
    for off in ("", "0", "false", "no"):
        monkeypatch.setenv("MKTG_TRACE", off)
        assert not tracing_enabled()
    monkeypatch.setenv("MKTG_TRACE", "1")
    assert tracing_enabled()

    trace = RunTrace(label="account brief")
    # Two routing hops emit only a function call, then the specialist answers
    # and both layers above it repeat that answer.
    for author, length in (
        ("marketing_orchestrator", 0),
        ("abm_orchestrator", 0),
        ("abm_account_intel", 10449),
        ("abm_orchestrator", 10402),
        ("marketing_orchestrator", 10510),
    ):
        trace.mark(author, length)
    report = "\n".join(trace.lines())
    assert "account brief" in report
    assert "events=5" in report
    assert "abm_account_intel" in report
    assert "the answer was emitted 3 times" in report

    # A single answer is the healthy case and must not be flagged.
    lean = RunTrace()
    lean.mark("marketing_orchestrator", 0)
    lean.mark("abm_account_intel", 10449)
    assert "was emitted" not in "\n".join(lean.lines())


def test_streaming_does_not_hijack_the_scroll_position() -> None:
    """Snapping to the bottom every tick fought a user reading further back."""
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function isChatNearBottom" in script
    assert "function scrollChat" in script
    assert "if (!force && !stickToBottom)" in script
    nav = script.split("function renderQueryNav()")[1].split("function highlightQueryNav")[0]
    assert "turn.scrollIntoView" not in nav
    assert "canvas.scrollTo" in nav
    sheet = client.get("/static/styles.css").text
    assert ".shell.is-artifact-open .query-nav" in sheet


def test_the_status_line_is_one_line_that_swaps_and_keeps_ticking() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    setter = script.split("function setStatus(node, label)")[1].split("\n}")[0]
    assert 'el("span", "status-label t-text-swap", label)' in setter
    assert 'node.querySelector(".status-label")' in setter
    sheet = client.get("/static/styles.css").text
    assert ".status {" in sheet


def test_a_task_still_scopes_which_filter_categories_are_live() -> None:
    """Availability follows the selected task's filter list."""
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function allowedFilterNames(task)" in script
    assert "function syncFilterAvailability()" in script
    assert "function policyCampaignTypes(task)" in script
    assert "task.filter_policy.categories" in script
    assert "if (item.type) input.dataset.type = item.type;" in script
    sync = script.split("function syncFilterAvailability()")[1].split("function findTask")[0]
    assert "policyTypes.includes(input.value)" in sync
    assert "selectedTypes.includes(rowType)" in sync
    assert "selectedAssets.includes(rowType)" in sync
    refresh = script.split("const refreshDraft = () => {")[1].split("filterOrg")[0]
    assert "syncFilterAvailability();" in refresh
    assert "function fillPrompt(template, values)" in script
    draft = script.split("function composeDraft(taskId)")[1].split("function syncTaskButtons()")[0]
    assert "Working filters:" not in draft
    launch = script.split("function applyLaunchPrompt(taskId)")[1].split("function returningToChat()")[0]
    assert "Working filters:" not in launch
    assert 'block.classList.toggle("is-collapsed", allOff)' in script
    assert ".filter-block.is-collapsed" in client.get("/static/styles.css").text or ".is-collapsed" in client.get("/static/styles.css").text


def test_the_filter_rail_is_a_single_scroll_region() -> None:
    """Account lists scroll inside the filter dialog, not nested pane caps."""
    client = _client([])
    sheet = client.get("/static/styles.css").text
    assert ".app-dialog-body {" in sheet
    assert ".chat-scroll-btn {" in sheet
    assert ".chat-content {" in sheet


def test_chat_task_uses_selected_marketing_context() -> None:
    message = compose_task_message(
        "campaign_performance",
        FilterSelection(
            campaigns=["CMP-002"],
            campaign_types=["Webinar"],
            asset_types=["Whitepaper"],
        ),
    )
    assert "Zero Trust Maturity" in message
    assert "Working filters:" not in message
    notes = filter_notes(
        FilterSelection(
            campaigns=["CMP-002"],
            campaign_types=["Webinar"],
            asset_types=["Whitepaper"],
            events=["EVT-001"],
            accounts=["ACC-001"],
        )
    )
    assert any("Campaign types: Webinar" in note for note in notes)
    assert any("Asset types: Whitepaper" in note for note in notes)
    assert any("Events:" in note and "Munich" in note for note in notes)
    assert any("Accounts:" in note and "Vantage" in note for note in notes)

    scoped_write = compose_task_message(
        "write_content",
        FilterSelection(campaigns=["CMP-002"]),
    )
    assert "Zero Trust" in scoped_write
    unscoped_write = compose_task_message("write_content", FilterSelection())
    assert "anchor asset" in unscoped_write.lower()

    canned_segment = compose_task_message("sixsense_segment", FilterSelection())
    assert "financial services" not in canned_segment.lower()
    assert "surging" not in canned_segment.lower()
    scoped_segment = compose_task_message(
        "sixsense_segment",
        FilterSelection(campaigns=["CMP-002"], accounts=["ACC-001"]),
    )
    assert "Zero Trust" in scoped_segment
    canned_create = compose_task_message("create_campaign", FilterSelection())
    assert "Create a webinar" not in canned_create
    scoped_create = compose_task_message(
        "create_campaign",
        FilterSelection(campaign_types=["Field Event"], campaigns=["CMP-002"]),
    )
    assert "Field Event" in scoped_create
    assert "Zero Trust" in scoped_create
    assert "Use exactly these values and call create_sfdc_campaign once:" in scoped_create
    assert "- Type: Field Event" in scoped_create
    assert "- Region: EMEA" in scoped_create
    assert "- Dates: 2026-06-21 to 2026-10-04" in scoped_create
    assert "- Budget: 22000 USD" in scoped_create
    assert "- Owner: omkar.patil@sailpoint.com" in scoped_create
    intel = compose_task_message(
        "abm_account_intel",
        FilterSelection(accounts=["ACC-001"]),
    )
    assert intel.lower().startswith("write an intel brief")
    geo_perf = compose_task_message(
        "campaign_performance",
        FilterSelection(geos=["EMEA"]),
    )
    assert "EMEA" in geo_perf
    assert "How did  perform" not in geo_perf
    assert "gap to pipeline target" in geo_perf.lower()
    ideas = compose_task_message(
        "campaign_ideation",
        FilterSelection(campaign_types=["Webinar"]),
    )
    assert "Webinar" in ideas
    assert "Zero Trust" not in ideas
    type_brief = compose_task_message(
        "campaign_brief",
        FilterSelection(campaign_types=["Webinar"]),
    )
    assert "Webinar" in type_brief
    assert "Zero Trust" not in type_brief
    ppt = compose_task_message(
        "campaign_ppt",
        FilterSelection(campaigns=["CMP-001"]),
    )
    assert "Generate a PPT" in ppt
    assert "Paid Social" in ppt


def test_chat_task_endpoint_streams_composed_prompt() -> None:
    client = _client([_event("analysis_campaign_performance", PLAIN_REPLY)])
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "task_id": "campaign_brief",
            "filters": {
                "campaigns": [],
                "campaign_types": ["Webinar"],
                "asset_types": [],
                "content": [],
            },
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "Webinar" in events[0]["text"]
    assert "Zero Trust" not in events[0]["text"]
    assert "Working filters:" not in events[0]["text"]


def test_chat_rejects_empty_message() -> None:
    client = _client([])
    response = client.post("/api/chat", json={"session_id": "x", "message": "   "})
    assert response.status_code == 400


def test_chat_prefers_edited_message_over_task_id() -> None:
    client = _client([_event("analysis_pipeline_health", PLAIN_REPLY)])
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "task_id": "pipeline_health",
            "message": "How is pipeline in APJ, and which deals are stalled?",
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "stalled" in events[0]["text"]


def test_chat_hides_filters_from_visible_prompt_but_sends_them_to_the_model() -> None:
    runner = FakeRunner([_event("analysis_campaign_performance", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "How did our campaigns perform this quarter?",
            "filters": {
                "campaigns": ["CMP-002"],
                "campaign_types": ["Webinar"],
                "asset_types": [],
                "content": [],
            },
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "Working filters:" not in events[0]["text"]
    assert runner.calls == 1
    assert "Working filters:" in runner.messages[0]
    assert "Webinar" in runner.messages[0]


def test_off_topic_chat_does_not_call_the_model() -> None:
    runner = FakeRunner([_event("analysis_pipeline_health", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "What's the weather in London?",
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert runner.calls == 0
    reply = next(event for event in events if event["type"] == "reply")
    assert "marketing work" in reply["text"].lower()


def test_write_guard_does_not_create_from_the_unscoped_draft() -> None:
    canned = compose_task_message("sixsense_segment", FilterSelection())
    assert write_guard_reply(canned) is not None
    assert "campaign" in write_guard_reply(canned).lower()
    assert write_guard_reply("Scope a 6sense segment for Glenmore.") is None
    assert (
        write_guard_reply(
            canned, FilterSelection(campaigns=["CMP-002"], accounts=["ACC-001"])
        )
        is None
    )
    create_default = compose_task_message("create_campaign", FilterSelection())
    assert write_guard_reply(create_default) == WRITE_GUARD_REPLY
    assert (
        write_guard_reply(
            create_default,
            FilterSelection(campaign_types=["Webinar"], campaigns=["CMP-002"]),
        )
        is None
    )

    runner = FakeRunner([_event("marketing_ops", "would create 6sense")])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "task_id": "sixsense_segment",
            "message": canned,
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert runner.calls == 0
    reply = next(event for event in events if event["type"] == "reply")
    assert reply["kind"] == "question"
    assert "tick" in reply["text"].lower()


def test_unscoped_account_intel_asks_for_a_filter_not_an_id() -> None:
    canned = compose_task_message("abm_account_intel", FilterSelection())
    asked = write_guard_reply(canned)
    assert asked is not None
    assert "account" in asked.lower()
    assert "acc-001" not in asked.lower()
    assert (
        write_guard_reply(canned, FilterSelection(accounts=["ACC-003"])) is None
    )

    runner = FakeRunner([_event("abm_account_intel", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": canned,
        },
    ) as response:
        body = "".join(response.iter_text())
    assert runner.calls == 0
    reply = next(event for event in _sse_events(body) if event["type"] == "reply")
    assert reply["kind"] == "question"
    assert "account" in reply["text"].lower()


def test_a_typed_account_id_is_in_scope_and_reaches_the_model() -> None:
    runner = FakeRunner([_event("abm_account_intel", PLAIN_REPLY)])
    store = _store()
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=store)
    )
    created = client.post("/api/session").json()
    chat_id = "intel-follow-up"
    canned = compose_task_message("abm_account_intel", FilterSelection())
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "chat_id": chat_id,
            "message": canned,
        },
    ) as response:
        "".join(response.iter_text())
    assert runner.calls == 0

    other = TestClient(
        create_app(
            runner=runner,
            session_service=InMemorySessionService(),
            chat_store=store,
        )
    )
    other_session = other.post("/api/session").json()["session_id"]
    with other.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": other_session,
            "chat_id": chat_id,
            "message": "Acc-003",
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert events[0]["text"] == "Acc-003"
    assert runner.calls == 1
    assert "ACC-003" in runner.messages[0]
    assert "Kestrel" in runner.messages[0]
    reply = next(event for event in events if event["type"] == "reply")
    assert "marketing work" not in reply["text"].lower()


def _reply_to(client: TestClient, session_id: str, message: str) -> dict:
    with client.stream(
        "POST",
        "/api/chat",
        json={"session_id": session_id, "message": message},
    ) as response:
        body = "".join(response.iter_text())
    return next(
        event for event in _sse_events(body) if event["type"] == "reply"
    )


def test_small_talk_is_answered_rather_than_refused() -> None:
    runner = FakeRunner([_event("analysis_pipeline_health", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    for message in ("hello", "Hi James!", "thanks", "who are you?"):
        reply = _reply_to(client, created["session_id"], message)
        assert "marketing work in this workspace" not in reply["text"]
    # Still free: small talk is answered from a canned string, not the model.
    assert runner.calls == 0


def test_a_greeting_carrying_a_real_question_reaches_the_model() -> None:
    runner = FakeRunner([_event("analysis_pipeline_health", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    created = client.post("/api/session").json()
    reply = _reply_to(
        client, created["session_id"], "hi, assess pipeline health for EMEA"
    )
    assert runner.calls == 1
    assert reply["text"] == PLAIN_REPLY


def test_thanks_does_not_strand_the_next_follow_up() -> None:
    runner = FakeRunner([_event("analysis_pipeline_health", PLAIN_REPLY)])
    client = TestClient(
        create_app(runner=runner, session_service=InMemorySessionService(), chat_store=_store())
    )
    session_id = client.post("/api/session").json()["session_id"]
    _reply_to(client, session_id, "assess pipeline health for EMEA")
    _reply_to(client, session_id, "thanks")
    # "what about AMER" is only in scope as a follow-up, so the acknowledgment
    # in between must have left the session's marketing context alone.
    _reply_to(client, session_id, "what about AMER")
    assert runner.calls == 2


def test_chat_accepts_csv_attachment() -> None:
    import base64

    sessions = InMemorySessionService()
    client = TestClient(
        create_app(
            runner=FakeRunner([_event("mops_list_load", PLAIN_REPLY)]),
            session_service=sessions,
            chat_store=_store(),
        )
    )
    created = client.post("/api/session").json()
    payload = base64.b64encode(b"email,company\na@b.com,Vantage\n").decode("ascii")
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "Load this list into Marketo.",
            "attachments": [
                {
                    "filename": "leads.csv",
                    "mime_type": "text/csv",
                    "content_base64": payload,
                }
            ],
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "leads.csv" in events[0]["text"]
    session = asyncio.run(
        sessions.get_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=created["session_id"],
        )
    )
    assert session is not None
    assert session.state[UPLOADED_LEAD_FILES_STATE]["leads.csv"][0] == {
        "email": "a@b.com",
        "company": "Vantage",
    }


def test_chat_transcript_is_stored_on_the_server() -> None:
    store = _store()
    client = _client(
        [_event("analysis_pipeline_health", PLAIN_REPLY)],
        chat_store=store,
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "chat_id": "chat-keep",
            "message": "How is our pipeline looking?",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["x-chat-id"] == "chat-keep"
        "".join(response.iter_text())
    listed = client.get("/api/chats").json()["chats"]
    assert listed[0]["id"] == "chat-keep"
    record = client.get("/api/chats/chat-keep").json()
    assert "pipeline" in record["turns"][0]["user"]
    assert record["turns"][0]["reply"]["kind"] == "plain"
    assert "1.46x" in record["turns"][0]["reply"]["text"]
    gone = client.delete("/api/chats/chat-keep")
    assert gone.status_code == 200
    assert client.get("/api/chats/chat-keep").status_code == 404


def test_a_pending_turn_stays_on_the_server_until_it_finishes() -> None:
    store = _store()
    store.append_user(
        chat_id="chat-keep",
        session_id="sess",
        title="Pipeline",
        user="How is our pipeline looking?",
        tags=[],
        filters={},
    )
    listed = store.list_chats()
    assert listed[0]["pending"] is True
    record = store.get("chat-keep")
    assert record["turns"][0]["reply"] is None
    assert record["turns"][0]["status"] == "pending"
    store.finish_reply("chat-keep", {"kind": "plain", "text": PLAIN_REPLY})
    record = store.get("chat-keep")
    assert record["turns"][0]["status"] == "done"
    assert "1.46x" in record["turns"][0]["reply"]["text"]
    assert store.list_chats()[0]["pending"] is False


def test_cancel_marks_a_pending_turn() -> None:
    store = _store()
    store.append_user(
        chat_id="chat-stop",
        session_id="sess",
        title="Pipeline",
        user="How is our pipeline looking?",
        tags=[],
        filters={},
    )
    client = TestClient(
        create_app(
            runner=FakeRunner([]),
            session_service=InMemorySessionService(),
            chat_store=store,
        )
    )
    stopped = client.post("/api/chats/chat-stop/cancel")
    assert stopped.status_code == 200
    record = client.get("/api/chats/chat-stop").json()
    assert record["turns"][0]["status"] == "cancelled"
    assert "cancelled" in record["turns"][0]["reply"]["text"].lower()


def test_chat_history_is_a_list_not_pills() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function relativeTime" in script
    assert "history-item-meta" in script
    assert "pendingChats.has(chat.id)" in script
    assert "updatedAt" in script
    sheet = client.get("/static/styles.css").text
    item = sheet.split(".history-item {", 1)[1].split("}", 1)[0]
    assert "border-radius: 10px" in item
    assert "999px" not in item
    assert ".history-row.is-active" in sheet
    assert ".history-row:hover .history-delete" in sheet
    chips = sheet.split(".selection-chip {", 1)[1].split("}", 1)[0]
    assert "border-radius: 999px" in chips


def test_workspace_resumes_a_pending_chat_from_the_server() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function resumePendingChat" in script
    assert "function paintTurnReply" in script
    assert "/api/chats/" in script
    assert "/cancel" in script
    restore = script.split("function restoreActiveChat()")[1].split("function historyTitle")[0]
    assert 'querySelectorAll(".turn.pending")' not in restore
    assert "resumePendingChat(chat.id)" in restore
    send_path = script.split("async function askJames")[1].split("async function ")[0]
    assert "resumePendingChat(chatId)" in send_path


def test_artifact_prose_is_structured_rather_than_dumped_into_a_pre() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function artifactBlock(body, kind)" in script
    assert "function looksLikeEmail" in script
    assert "function fenceEmails" in script
    sheet = client.get("/static/styles.css").text
    assert ".md-prose .artifact" in sheet or ".artifact {" in sheet
    assert ".artifact-library" in sheet
    assert ".artifact-pane" in sheet
    assert ".artifact-chip" in sheet
    assert ".artifact-chip-download" in sheet
    assert ".artifact-resize" in sheet
    artifacts = client.get("/static/artifacts.js").text
    assert "expandIcon.hidden = paneExpanded" in artifacts
    assert "function resolveItem" in artifacts
    assert "kindIcon," in artifacts
    assert ".artifact-pane-head" in sheet
    assert "height: var(--bar-height)" in sheet


def test_recommended_actions_render_as_a_numbered_list() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert 'el("div", "action-row")' in script
    assert 'el("p", "action-text")' in script
    # The steps carry a visible number, so three actions do not read as three
    # unrelated paragraphs.
    assert 'el("span", "action-index", String(step))' in script
    sheet = client.get("/static/styles.css").text
    assert ".action-row" in sheet or ".action-text" in sheet
    assert ".action-index {" in sheet


def test_a_briefing_reads_as_prose_rather_than_a_ransom_note() -> None:
    """The figures in a sentence kept switching to the mono face, the section
    headings were 10px, and the opening sentence was printed twice."""
    client = _client([])
    script = client.get("/static/app.js").text
    assert "function summaryTail(summary, lead)" in script
    briefing = script.split("function renderBriefing(payload, options = {})")[1].split(
        "function renderReceipt"
    )[0]
    # The lead line and the card body are two halves of one summary.
    assert "const lead = " in briefing
    assert "summaryTail(payload.summary, lead)" in briefing
    assert "appendRich(summaryText, payload.summary)" not in briefing

    sheet = client.get("/static/styles.css").text
    inline_num = sheet.split(".num {")[1].split("}")[0]
    assert "font-family: inherit" in inline_num
    assert "tabular-nums" in inline_num
    # The mono face is still right for a standalone metric tile.
    assert "font-family: var(--num)" in sheet.split(".metric-value {")[1].split("}")[0]
    # A section title matches the body it introduces and separates itself by
    # weight, not by shrinking into an uppercase caption.
    heading = sheet.split(".card h3 {")[1].split("}")[0]
    assert "font-size: 16px" in heading
    assert "font-weight: 700" in heading
    assert "text-transform: none" in heading
    body = sheet.split(".card p,")[1].split("}")[0]
    assert "font-size: 16px" in body
    prose_heading = sheet.split(".md-prose h2,")[1].split("}")[0]
    assert "font-weight: 700" in prose_heading
    for level in (".md-prose h2 {", ".md-prose h3 {", ".md-prose h4 {"):
        # The last match is the standalone rule; the first is the shared group.
        assert "font-size: 1rem" in sheet.split(level)[-1].split("}")[0], level


def test_the_summary_lead_only_splits_on_a_sentence_boundary() -> None:
    """The summary paragraph was starting mid-word.

    The lead took the first "." at any position, so "brief.json.md" ended the
    sentence, and when no terminator appeared early it cut at a fixed character
    count. Either way the rest of the summary began inside a word.
    """
    script = _client([]).get("/static/app.js").text
    spoken = script.split("function spokenLine(summary)")[1].split("function summaryTail")[0]
    # A terminator only counts when a space or the end of the line follows it.
    assert "[.!?](?=\\s|$)" in spoken
    # No character-count fallback: without a clean sentence there is no lead.
    assert "slice(0, 160)" not in spoken
    assert 'return sentence ? sentence[0].trim() : "";' in spoken
    tail = script.split("function summaryTail(summary, lead)")[1].split("function rememberLastJob")[0]
    assert "if (rest && !/^\\s/.test(rest)) return text;" in tail


def test_the_thinking_row_is_a_disclosure_line_not_a_card() -> None:
    """A chevron and a muted line above the answer, the way Gemini shows it."""
    client = _client([])
    sheet = client.get("/static/styles.css").text
    panel = sheet.split("\n.reasoning {")[1].split("}")[0]
    assert "border: 0" in panel
    assert "background: transparent" in panel
    trigger = sheet.split(".reasoning-trigger {")[1].split("}")[0]
    assert "justify-content: flex-start" in trigger
    # The chevron leads the line and survives the answer landing, because it is
    # what says the thinking can be reopened.
    assert "trigger.append(chevron, triggerLabel)" in client.get("/static/app.js").text
    assert '.reasoning[data-done="true"]:not(.is-open) .reasoning-chevron' not in sheet


def test_prose_lists_have_room_and_muted_markers() -> None:
    sheet = _client([]).get("/static/styles.css").text
    item = sheet.split(".md-prose li {")[1].split("}")[0]
    assert "margin: 0.5em 0" in item
    assert ".md-prose li::marker" in sheet
    assert ".card li::marker" in sheet


def test_a_reply_reads_as_a_document_not_a_boxed_report() -> None:
    """Gemini and Claude run the answer straight down the column. The frame and
    the rules between sections were doing the work that whitespace should."""
    sheet = _client([]).get("/static/styles.css").text
    # Anchored, so this does not match ".bubble.plain .briefing {".
    briefing = sheet.split("\n.briefing {")[1].split("}")[0]
    assert "border: 0" in briefing
    assert "background: transparent" in briefing
    assert "padding: 0" in briefing
    # Sections are spaced apart rather than ruled off from each other.
    assert ".briefing .card + .card {" not in sheet
    # The reply column supplies the inset the frame used to provide.
    assert ".turn-assistant .reply {" in sheet


def test_a_ticked_filter_is_marketing_context_for_a_short_question() -> None:
    """"tell me more about" + a campaign tag is a request, not off-topic chat."""
    runner = FakeRunner([_event("analysis_campaign_performance", PLAIN_REPLY)])
    client = TestClient(
        create_app(
            runner=runner,
            session_service=InMemorySessionService(),
            chat_store=_store(),
        )
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "tell me more about",
            "filters": {"campaigns": ["CMP-002"]},
        },
    ) as response:
        body = "".join(response.iter_text())
    reply = next(e for e in _sse_events(body) if e["type"] == "reply")
    assert runner.calls == 1
    assert reply["text"] == PLAIN_REPLY
    # The selected campaign reaches the model even though the text omits it.
    assert "Working filters:" in runner.messages[0]

    # Nothing ticked and no marketing words: still refused without a call.
    bare = FakeRunner([_event("analysis_campaign_performance", PLAIN_REPLY)])
    bare_client = TestClient(
        create_app(
            runner=bare,
            session_service=InMemorySessionService(),
            chat_store=_store(),
        )
    )
    session_id = bare_client.post("/api/session").json()["session_id"]
    with bare_client.stream(
        "POST",
        "/api/chat",
        json={"session_id": session_id, "message": "tell me more about"},
    ) as response:
        refused = "".join(response.iter_text())
    assert bare.calls == 0
    assert "only handle marketing work" in refused

    # A ticked filter does not launder a genuinely off-topic question.
    weather = FakeRunner([_event("analysis_campaign_performance", PLAIN_REPLY)])
    weather_client = TestClient(
        create_app(
            runner=weather,
            session_service=InMemorySessionService(),
            chat_store=_store(),
        )
    )
    session_id = weather_client.post("/api/session").json()["session_id"]
    with weather_client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "what is the weather in Munich",
            "filters": {"campaigns": ["CMP-002"]},
        },
    ) as response:
        "".join(response.iter_text())
    assert weather.calls == 0


def test_composer_shows_attachment_errors() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    assert "const MAX_ATTACH = 5;" in script
    assert "const MAX_ATTACH_BYTES = 8 * 1024 * 1024;" in script
    assert "function readFileAsAttachment(file)" in script
    home = client.get("/chat").text
    assert 'id="attach-chips"' in home
    assert 'id="attach"' in home


def test_cleanup_workspace_shell_is_served() -> None:
    client = _client([])
    home = client.get("/chat").text
    sheet = client.get("/static/styles.css").text
    assert 'id="command-palette"' not in home
    assert 'id="open-tasks"' in home
    assert 'id="open-filters"' in home
    assert 'id="open-accounts"' not in home
    assert 'id="toggle-sidebar"' in home
    assert 'class="sidebar-nav-item sidebar-new-chat"' in home
    assert 'class="workspace-bar"' in home
    assert '<span class="bar-fullname">James the Marketing Minion</span>' in home
    assert 'id="composer-drop"' in home
    assert 'href="/dashboard"' in home
    assert 'id="nav-artifacts"' in home
    assert 'id="artifact-library"' in home
    dash = client.get("/dashboard").text
    assert 'id="dashboard"' in dash
    assert 'id="nav-artifacts"' in dash
    assert 'href="/chat?view=artifacts"' in dash
    assert 'id="chart-type"' in dash
    assert 'id="filter-geos"' in dash
    assert "Spend" in dash
    assert '<span class="bar-fullname">James the Marketing Minion</span>' in dash
    assert "Opp size" not in dash
    assert "SS stage" not in dash
    assert client.get("/app").text == dash
    payload = client.get("/api/dashboard").json()
    assert "kpis" in payload
    assert "campaigns" in payload
    assert payload["filters"]["geos"]
    assert payload["defaults"]["geo"] == "EMEA"
    assert payload["copy"]["kpi_pipeline"] == "Gap to target"
    assert payload["copy"]["kpi_open_hint"] == "Match these filters"
    assert payload["copy"]["kpi_week_hint"] == "Need a follow-up"
    assert payload["copy"]["kpi_slack"] == "Slack"
    assert payload["copy"]["kpi_slack_hint"] == "Open the feed"
    assert "days left in the quarter" in payload["copy"]["kpi_pipeline_hint"]
    assert "in view" in payload["copy"]["kpi_pipeline_hint"]
    assert payload["kpis"]["spend"] >= 0
    mixed_spend = payload["by_spend"]
    sized = client.get("/api/dashboard?spend=mid").json()
    assert sized["kpis"]["open_campaigns"] <= payload["kpis"]["open_campaigns"]
    assert [row["id"] for row in sized["by_spend"]] == [row["id"] for row in mixed_spend]
    assert sized["by_spend"] == mixed_spend
    assert "function chartFill(colors, id, catalog)" in client.get("/static/dashboard.js").text
    assert payload["kpis"]["closing_week"] >= 1
    assert payload["kpis"]["days_left"] >= 0
    assert any(item["id"] == "smb" for item in payload["filters"]["spend"])
    assert any(item.get("campaign") for item in payload["notifications"])
    assert any(item["id"] == "abm_account_selection" for item in payload["tasks"])
    assert any(item.get("next_task") for item in payload["tasks"])
    for rail in (payload["tasks"], payload["notifications"]):
        assert rail
        for item in rail:
            assert item.get("detail")
            assert item.get("impact")
            assert item.get("prompt")
    assert payload["slack"]
    for item in payload["slack"]:
        assert item.get("channel", "").startswith("#")
        assert item.get("author")
        assert item.get("initials")
        assert " at " in item["when"]
        assert item.get("text")
        assert not str(item["author"]).startswith("@")
        assert "id" not in item
        assert "impact" not in item
        assert "prompt" not in item
    assert any(
        item.get("campaign") and item["campaign"] in item["prompt"]
        for item in payload["tasks"]
        if item.get("campaign")
    )
    dash_script = client.get("/static/dashboard.js").text
    chat_script = client.get("/static/app.js").text
    assert "function renderSlack(root, items)" in dash_script
    assert 'class="dash-slack"' in dash
    assert 'const label = score >= 70 ? "On track" : score >= 45 ? "Watch" : "Off";' in dash_script
    assert "function stashLaunch(item)" in dash_script
    assert "function dashScopeParams()" in dash_script
    assert 'params.set("spend"' in dash_script
    assert 'params.set("windows"' in dash_script
    assert 'due: "Continue"' in dash_script
    assert "gru-last-job" in chat_script
    assert "function setTableSort(key)" in dash_script
    assert "dash-camp-name" in dash_script
    assert "is-continue" in dash_script
    assert "function renderRailCounts(payload)" in dash_script
    assert "function renderChips()" not in dash_script
    sheet = client.get("/static/styles.css").text
    assert ".dash-sort {" in sheet
    sidebar_body = sheet.split(".sidebar-body {")[1].split("}")[0]
    assert "min-width: 0;" in sidebar_body
    assert "overflow-x: hidden;" in sidebar_body
    history_item = sheet.split(".history-item {")[1].split("}")[0]
    assert "width: 100%;" in history_item
    actions = sheet.split(".history-actions {")[1].split("}")[0]
    assert "position: absolute;" in actions
    assert "linear-gradient" in actions
    assert ".dash-chips {" not in sheet
    assert "color: var(--fg);" in sheet.split(".dash-kpi-value {")[1].split("}")[0]
    chat_script = client.get("/static/app.js").text
    assert "function nextJobButton()" in chat_script
    assert "function fillPlaceholderJobs()" not in chat_script
    assert "continueLastJobButton" not in chat_script
    assert "params.get(\"campaign\")" in chat_script
    assert "params.get(\"spend\")" in chat_script
    assert "params.get(\"windows\")" in chat_script
    assert "function scopeHintLine()" in chat_script
    assert "function retryTurn(turn)" in chat_script
    assert "function renderReceipt(payload)" in chat_script
    assert "function renderQuestion(payload)" in chat_script
    assert "function shouldOfferNextJob(event)" in chat_script
    assert "function renderCannot(payload)" in chat_script
    assert "const liveChats = new Set()" in chat_script
    assert 'el("button", "reply-action"' in chat_script
    assert ".reply-action {" in sheet
    assert "sample-badge" in chat_script
    assert "saveReplyAsNote" in chat_script
    assert "james-launch" in chat_script
    assert ".bubble.user" in sheet
    assert ".turn:nth-of-type(3n + 2) .bubble.user" in sheet
    assert "html[data-theme=\"dark\"] .bubble.user" in sheet
    assert "background: var(--user-bubble)" in sheet
    assert ".placeholder-actions" in sheet
    assert "justify-self: stretch" in sheet
    assert "flex-wrap: nowrap" in sheet
    assert ".placeholder-choice" in sheet
    assert "0 0 14px 2px" in sheet
    assert ".bar-sp-logo-dark" in sheet
    assert ".placeholder-continue" not in sheet
    assert ".composer::before" in sheet
    assert ".briefing-voice" in sheet
    assert ".task-group" in sheet
    assert ".task-menu-subhead" in sheet
    assert ".shell.is-empty" in sheet
    assert ".app-dialog-field" in sheet
    assert "function syncEmptyShell()" in chat_script
    assert "Let’s get some work done!" in chat_script
    assert 'dataset.theme === "dark"' in dash_script
    assert "command palette" not in home.lower()


def test_pinned_chats_sort_above_recents() -> None:
    store = _store()
    _seed_chat(store, "older", "Older")
    _seed_chat(store, "newer", "Newer")
    assert store.list_chats()[0]["id"] == "newer"
    store.patch_chat("older", pinned=True)
    _seed_chat(store, "newer", "Newer", user="Follow-up")
    listed = store.list_chats()
    assert listed[0]["id"] == "older"
    assert listed[0]["pinned"] is True
    store.patch_chat("older", pinned=False)
    _seed_chat(store, "newer", "Newer", user="Another follow-up")
    assert store.list_chats()[0]["id"] == "newer"
    assert store.list_chats()[0]["pinned"] is False


def test_prune_keeps_pinned_and_collection_chats() -> None:
    store = ChatStore(Path(tempfile.mkdtemp()) / "chats", limit=2)
    _seed_chat(store, "pinned", "Pinned")
    store.patch_chat("pinned", pinned=True)
    _seed_chat(store, "foldered", "Foldered")
    store.patch_chat("foldered", collection_id="col-keep")
    _seed_chat(store, "one", "One")
    _seed_chat(store, "two", "Two")
    _seed_chat(store, "three", "Three")
    ids = {row["id"] for row in store.list_chats()}
    assert "pinned" in ids
    assert "foldered" in ids
    assert store.get("pinned") is not None
    assert store.get("foldered") is not None


def test_patch_chat_pin_and_collection() -> None:
    store = _store()
    folders = _folders()
    folder = folders.create("APAC launch")
    _seed_chat(store, "chat-keep", "Pipeline")
    client = _client([], chat_store=store, collection_store=folders)
    pinned = client.patch("/api/chats/chat-keep", json={"pinned": True})
    assert pinned.status_code == 200
    assert pinned.json()["pinned"] is True
    moved = client.patch("/api/chats/chat-keep", json={"collection_id": folder["id"]})
    assert moved.status_code == 200
    assert moved.json()["collection_id"] == folder["id"]
    listed = client.get("/api/chats").json()["chats"]
    assert listed[0]["id"] == "chat-keep"
    assert listed[0]["pinned"] is True
    missing = client.patch("/api/chats/chat-keep", json={"collection_id": "nope"})
    assert missing.status_code == 404
    named = client.patch("/api/chats/chat-keep", json={"title": "  Q4 pipeline  "})
    assert named.status_code == 200
    assert named.json()["title"] == "Q4 pipeline"
    empty = client.patch("/api/chats/chat-keep", json={"title": "   "})
    assert empty.status_code == 400
    store.append_user(
        chat_id="chat-keep",
        session_id="sess",
        title="Should not stick",
        user="A later prompt",
        tags=[],
        filters={},
    )
    assert store.get("chat-keep")["title"] == "Q4 pipeline"


def test_collections_crud_ungroups_chats() -> None:
    store = _store()
    folders = _folders()
    _seed_chat(store, "chat-keep", "Pipeline")
    client = _client([], chat_store=store, collection_store=folders)
    created = client.post("/api/collections", json={"name": "APAC launch"})
    assert created.status_code == 200
    folder_id = created.json()["id"]
    client.patch(f"/api/chats/chat-keep", json={"collection_id": folder_id})
    renamed = client.patch(f"/api/collections/{folder_id}", json={"name": "EMEA launch"})
    assert renamed.json()["name"] == "EMEA launch"
    names = [row["name"] for row in client.get("/api/collections").json()["collections"]]
    assert names == ["EMEA launch"]
    gone = client.delete(f"/api/collections/{folder_id}")
    assert gone.status_code == 200
    assert client.get("/api/collections").json()["collections"] == []
    assert store.get("chat-keep") is not None
    assert store.get("chat-keep")["collection_id"] == ""


def test_sidebar_renders_pins_and_collections() -> None:
    client = _client([])
    script = client.get("/static/app.js").text
    history = script.split("function renderHistory()")[1].split("function isRecentsOpen")[0]
    assert history.index("block(\"Collections\")") < history.index("block(\"Pinned\")")
    assert "sidebar-new-collection" in history
    assert "All collections" in history
    assert "Show less" in history
    assert "M4 20h16a2 2 0 0 0 2-2V8" in history
    assert 'el("span", "", "Chats")' in history
    assert "function askRenameChat" in script
    assert 'collectionPromptMode = "rename-chat"' in script
    assert "canvas.querySelectorAll(\".turn\").length === 1" in script
    assert "function forgetImportedChats" in script
    assert "chatPayload.chats.map((row) => [row.id, row])" in script
    assert "New collection" in script
    assert "Remove from collection" in script
    assert '"Ungrouped"' not in script
    assert "M12 17v5M9 3h6v7.8" in script
    assert "activeCollectionId" in script
    assert 'next.set("collection"' in script
    sheet = client.get("/static/styles.css").text
    assert ".sidebar-new-collection" in sheet
    assert "border-radius: 999px" in sheet.split(".sidebar-new-collection {", 1)[1].split("}", 1)[0]
    assert ".collection-all" in sheet
    assert ".collection-group.is-active .collection-head" not in sheet
    assert "padding: 4px 2px 6px 18px" in sheet
    assert ".history-pin" in sheet
    assert ".sidebar-nav + .sidebar-nav" in sheet
    assert ".history-block" in sheet
    assert ".chats-head" in sheet
    assert ".chat-recents-row" in sheet
    assert 'el("section", "history-block")' in script
    assert "function showRecents()" in script
    assert "openSurface(chatRecents)" in script
    assert "M7 17L17 7M10 7h7v7" in script
    assert "function openChatSortMenu(anchor)" in script
    assert "CHAT_LIST_KEY = \"gru-chat-list\"" in script
    assert "Group by" in script
    assert "Last activity" in script
    page = client.get("/chat").text
    assert 'id="chat-recents"' in page
    assert "Chats and tasks" in page
    assert 'id="chat-recents-select"' in page
    assert 'id="chat-sort-dialog"' in page
    assert "collection-prompt-form" in page
    assert "Could not save that collection" in script
    assert 'id="confirm-delete-chat"' in page
    assert "app-dialog-btn-danger" in page
    assert 'id="move-collection-dialog"' in page
    assert ".app-dialog .app-dialog-btn-danger" in sheet
    assert "background: #cc27b0;" in sheet
    assert "Projects" not in page
    assert 'id="chat-history"' in page
