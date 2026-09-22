import pytest
from henry_dsr_agent.agents import AccountQuestionAgent, AccountQuestionTopic
from henry_dsr_agent.orchestrator import HenryOrchestrator

APEX = "001APEXFIN000001"
MERIDIAN = "001MERIDIAN00002"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("what is the stage of this account", AccountQuestionTopic.STAGE),
        ("what are my tasks left for this account", AccountQuestionTopic.TASKS),
        ("who should I call?", AccountQuestionTopic.CONTACTS),
        ("is this deal at risk", AccountQuestionTopic.RISK),
        ("how much is this deal worth?", AccountQuestionTopic.DEAL_VALUE),
        ("what tech do they use", AccountQuestionTopic.TECHNOLOGY),
        ("what's the intent score", AccountQuestionTopic.INTENT),
        ("who owns this account", AccountQuestionTopic.OWNERSHIP),
        ("when did we last touch them?", AccountQuestionTopic.ACTIVITY),
        ("tell me about this account", AccountQuestionTopic.OVERVIEW),
    ],
)
def test_questions_are_recognized(message: str, expected: AccountQuestionTopic) -> None:
    question = AccountQuestionAgent().classify(message)
    assert question is not None
    assert question.topic is expected


@pytest.mark.parametrize(
    "message",
    [
        "practice my pitch",
        "draft outreach for this account",
        "build me a proposal",
        "create a task to send the security pack",
        "",
    ],
)
def test_deliverable_requests_are_left_to_the_catalog(message: str) -> None:
    assert AccountQuestionAgent().classify(message) is None


@pytest.mark.asyncio
async def test_question_answers_instead_of_running_the_selected_task() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {
            "message": "what is the stage of this account",
            "account_id": APEX,
            "action": "top_prospect_accounts",
        }
    )
    assert "Apex Financial is at stage SS20" in result.markdown
    assert "Top Prospect" not in result.markdown
    assert result.data["answer"]["topic"] == "stage"


@pytest.mark.asyncio
async def test_account_named_in_the_message_outranks_the_selected_one() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {"message": "what stage is Meridian Health Network in?", "account_id": APEX}
    )
    assert "Meridian Health Network is at stage SS40" in result.markdown
    assert result.data["answer"]["account_name"] == "Meridian Health Network"


@pytest.mark.asyncio
async def test_typed_request_overrides_a_stale_task_selection() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {
            "message": "help me practice my pitch",
            "account_id": APEX,
            "action": "top_prospect_accounts",
        }
    )
    assert result.data["ask"]["action"] == "pitch_practice"


@pytest.mark.asyncio
async def test_menu_selection_still_runs_its_own_action() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {
            "message": "Rank my best prospects",
            "account_id": APEX,
            "action": "account_plan",
            "action_locked": True,
        }
    )
    assert result.data["ask"]["action"] == "account_plan"


@pytest.mark.asyncio
async def test_selected_task_still_answers_a_message_with_no_intent() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {"message": "go ahead", "account_id": APEX, "action": "pitch_practice"}
    )
    assert result.data["ask"]["action"] == "pitch_practice"


@pytest.mark.asyncio
async def test_task_questions_read_the_client_task_board() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {
            "message": "what are my tasks left for this account?",
            "account_id": APEX,
            "context": {
                "tasks": [
                    {
                        "account_id": APEX,
                        "account_name": "Apex Financial",
                        "items": [
                            {"text": "Send the SOC 2 pack", "done": False},
                            {"text": "Book the exec briefing", "done": True},
                        ],
                    }
                ]
            },
        }
    )
    assert "1 of 2 tasks is still open for Apex Financial" in result.markdown
    assert "Send the SOC 2 pack" in result.markdown
    assert "~~Book the exec briefing~~" in result.markdown


@pytest.mark.asyncio
async def test_task_question_reports_an_empty_list_for_a_new_account() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {"message": "what tasks are left?", "account_id": MERIDIAN}
    )
    assert "no tasks saved for Meridian Health Network" in result.markdown


@pytest.mark.asyncio
async def test_task_question_summarizes_every_account_when_none_is_selected() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat(
        {
            "message": "what tasks do I have?",
            "context": {
                "tasks": [
                    {
                        "account_id": APEX,
                        "account_name": "Apex Financial",
                        "items": [{"text": "Send the SOC 2 pack", "done": False}],
                    },
                    {
                        "account_id": MERIDIAN,
                        "account_name": "Meridian Health Network",
                        "items": [{"text": "Confirm the close plan", "done": True}],
                    },
                ]
            },
        }
    )
    assert "1 task still open across 2 accounts" in result.markdown
    assert "Meridian Health Network** — 0 open, 1 done" in result.markdown


@pytest.mark.asyncio
async def test_question_without_an_account_asks_for_one() -> None:
    orchestrator = HenryOrchestrator()
    result = await orchestrator.chat({"message": "what is the stage?"})
    assert result.data["answer"]["needs_account_selection"] is True
    assert "need an account" in result.markdown


@pytest.mark.asyncio
async def test_risk_answers_use_the_canonical_record_not_the_posted_copy() -> None:
    orchestrator = HenryOrchestrator()
    posted = {
        "id": MERIDIAN,
        "name": "Meridian Health Network",
        "domain": "meridianhealth.org",
        "bva_complete": True,
        "stakeholder_count": 3,
        "last_activity_date": "2026-09-01",
    }
    result = await orchestrator.chat(
        {"message": "is this deal at risk?", "account_id": MERIDIAN, "context": {"account": posted}}
    )
    assert "Missing Bva" not in result.markdown


@pytest.mark.asyncio
async def test_deal_risk_reads_bva_complete_and_stakeholder_count_on_dicts() -> None:
    from henry_dsr_agent.agents.deal_risk import DealRiskAgent
    from henry_dsr_agent.orchestrator import HenryOrchestrator

    mer = next(
        item
        for item in HenryOrchestrator()._all_accounts()
        if str(item.id) == MERIDIAN
    )
    posted = mer.model_dump()
    result = await DealRiskAgent().run(opportunity=posted)
    assert result.risk_level == "low"
    assert [flag.code for flag in result.flags] == []
