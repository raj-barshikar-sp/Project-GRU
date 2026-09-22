"""Natural-language routing and workflow orchestration for Henry."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

try:
    from ..agents import (
        AccountIntelAgent,
        AccountQuestion,
        AccountQuestionAgent,
        CompetitivePositioningAgent,
        DealRiskAgent,
        DSRAskCatalogAgent,
        IntentScorerAgent,
        LLMProvider,
        OutreachGeneratorAgent,
    )
    from ..agents.base import invoke_tool, model_dump, value
    from ..tools import BattlecardTool, IntentTool, SFDCTool, ZoomInfoTool
except ImportError:  # Support importing ``orchestrator`` as a top-level package.
    from agents import (  # type: ignore[import-not-found,no-redef]
        AccountIntelAgent,
        AccountQuestion,
        AccountQuestionAgent,
        CompetitivePositioningAgent,
        DealRiskAgent,
        DSRAskCatalogAgent,
        IntentScorerAgent,
        LLMProvider,
        OutreachGeneratorAgent,
    )
    from agents.base import (  # type: ignore[import-not-found,no-redef]
        invoke_tool,
        model_dump,
        value,
    )
    from tools import (  # type: ignore[import-not-found,no-redef]
        BattlecardTool,
        IntentTool,
        SFDCTool,
        ZoomInfoTool,
    )

from .graph import StateGraph

if TYPE_CHECKING:
    try:
        from ..schemas import (  # noqa: F401
            Battlecard,
            ContactPersona,
            IntentSignal,
            SalesforceAccount,
            TechnographicIntel,
        )
    except ImportError:
        from schemas import (  # type: ignore[import-not-found,no-redef]  # noqa: F401
            Battlecard,
            ContactPersona,
            IntentSignal,
            SalesforceAccount,
            TechnographicIntel,
        )


class WorkflowIntent(str, Enum):
    """Workflows understood by the deterministic natural-language router."""

    PROSPECTING = "prospecting"
    DISCOVERY = "discovery"
    OUTREACH = "outreach"
    DEAL_RISK = "deal_risk"
    ACCOUNT = "account"


class OrchestrationResult(BaseModel):
    """Typed public response from an orchestrated request."""

    intent: WorkflowIntent
    markdown: str
    data: dict[str, Any]


class HenryOrchestrator:
    """Route seller requests through small, composable asynchronous workflows."""

    def __init__(
        self,
        *,
        sfdc_tool: Any | None = None,
        intent_tool: Any | None = None,
        zoominfo_tool: Any | None = None,
        battlecard_tool: Any | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.sfdc_tool = sfdc_tool or SFDCTool()
        self.intent_tool = intent_tool or IntentTool()
        self.zoominfo_tool = zoominfo_tool or ZoomInfoTool()
        self.battlecard_tool = battlecard_tool or BattlecardTool()
        self.intent_scorer = IntentScorerAgent(llm=llm)
        self.account_intel = AccountIntelAgent(zoominfo_tool=self.zoominfo_tool, llm=llm)
        self.positioning = CompetitivePositioningAgent(
            battlecard_tool=self.battlecard_tool, llm=llm
        )
        self.outreach_agent = OutreachGeneratorAgent(llm=llm)
        self.deal_risk_agent = DealRiskAgent(llm=llm)
        self.dsr_ask_catalog = DSRAskCatalogAgent()
        self.account_questions = AccountQuestionAgent()

    def classify_intent(self, request: str) -> WorkflowIntent:
        """Classify a seller request using deterministic, explainable keywords."""
        text = request.lower()
        rules: tuple[tuple[WorkflowIntent, tuple[str, ...]], ...] = (
            (
                WorkflowIntent.DEAL_RISK,
                ("deal risk", "at risk", "stale deal", "opportunity health", "pipeline risk"),
            ),
            (
                WorkflowIntent.OUTREACH,
                ("outreach", "write email", "draft email", "cold email", "linkedin", "call script"),
            ),
            (
                WorkflowIntent.PROSPECTING,
                ("prospect", "prioritize", "intent score", "rank account", "hot account"),
            ),
            (
                WorkflowIntent.DISCOVERY,
                ("discovery", "talk track", "competitive", "battlecard", "landmine"),
            ),
        )
        for intent, markers in rules:
            if any(marker in text for marker in markers):
                return intent
        return WorkflowIntent.ACCOUNT

    async def run(
        self,
        request: str,
        *,
        account_id: str | None = None,
        opportunity_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Classify ``request``, execute its graph, and synthesize Markdown."""
        intent = self.classify_intent(request)
        initial = dict(context or {})
        initial.update(
            {
                "request": request,
                "account_id": account_id or initial.get("account_id"),
                "opportunity_id": opportunity_id or initial.get("opportunity_id"),
            }
        )
        if (
            intent == WorkflowIntent.PROSPECTING
            and not initial.get("account_id")
            and initial.get("account") is None
        ):
            return await self._prospect_territory(initial)
        graph = self._build_graph(intent)
        state = await graph.run(initial)
        public_data = {
            key: self._serializable(item)
            for key, item in state.items()
            if key
            not in {
                "request",
                "account_id",
                "opportunity_id",
                "contacts",
                "technographics",
                "battlecards",
            }
        }
        return OrchestrationResult(
            intent=intent,
            markdown=self._synthesize(intent, state),
            data=public_data,
        )

    async def chat(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Route a free-text message to the capability that actually answers it.

        The message always decides. A menu selection only sets the default for a
        message that expresses no intent of its own, and an account named in the
        message outranks the one selected in the UI. Requests that arrive with
        ``action_locked`` come straight from a menu click and skip the routing.
        """
        normalized = self._payload(payload)
        message = str(normalized.get("message") or "")
        normalized = self._with_named_account(normalized)
        if not normalized.get("action_locked"):
            question = self.account_questions.classify(message)
            if question is not None:
                return await self._answer_question(question, normalized)
        classification = self.dsr_ask_catalog.classify(message)
        if normalized.get("action") or not classification.is_default:
            return await self.ask(normalized)
        return await self.run(
            message or "research account",
            account_id=normalized.get("account_id"),
            opportunity_id=normalized.get("opportunity_id"),
            context=normalized.get("context"),
        )

    async def _answer_question(
        self, question: AccountQuestion, normalized: Mapping[str, Any]
    ) -> OrchestrationResult:
        """Answer a recognized account question from the joined local records."""
        account = normalized.get("account")
        intent: Any | None = None
        technographics: Any | None = None
        risk: Any | None = None
        if account is not None:
            signals, technographics, risk = await self._account_records(account)
            intent = signals[0] if signals else None
        answer = await self.account_questions.run(
            question,
            account=account,
            intent=intent,
            technographics=technographics,
            deal_risk=risk,
            task_board=self._task_board(normalized),
        )
        return OrchestrationResult(
            intent=WorkflowIntent.ACCOUNT,
            markdown=answer.markdown,
            data={"answer": self._serializable(answer)},
        )

    async def ask(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Execute any action in the complete local DSR ask catalog."""
        normalized = self._payload(payload)
        context = normalized["context"]
        accounts = list(self._all_accounts())
        account = self._canonical_account(
            normalized.get("account") or context.get("account"), accounts
        )
        account_id = normalized.get("account_id")
        if account is None and account_id:
            account = next(
                (
                    item
                    for item in accounts
                    if str(value(item, "id")) == str(account_id)
                ),
                None,
            )

        intent = None
        signals: list[Any] = []
        intent_repository = getattr(self.intent_tool, "_repository", None)
        if intent_repository is not None:
            signals = list(intent_repository.all())
        technographics = None
        risk = None
        if account is not None:
            matches, technographics, risk = await self._account_records(account)
            intent = matches[0] if matches else None

        card_repository = getattr(self.battlecard_tool, "_repository", None)
        battlecards = list(card_repository.all()) if card_repository is not None else []
        message = str(normalized.get("message") or "")
        requested_action = self._arbitrate_action(normalized, message)
        try:
            result = await self.dsr_ask_catalog.run(
                message,
                requested_action=requested_action,
                account=account,
                accounts=accounts,
                intent=intent,
                signals=signals,
                technographics=technographics,
                battlecards=battlecards,
                deal_risk=risk,
            )
        except ValueError:
            result = await self.dsr_ask_catalog.run(
                message,
                account=account,
                accounts=accounts,
                intent=intent,
                signals=signals,
                technographics=technographics,
                battlecards=battlecards,
                deal_risk=risk,
            )
        return OrchestrationResult(
            intent=WorkflowIntent.ACCOUNT,
            markdown=result.markdown,
            data={"ask": self._serializable(result)},
        )

    async def ask_catalog(self) -> dict[str, Any]:
        """Return catalog metadata for API, CLI, and future clients."""
        return {
            "actions": [
                self._serializable(entry) for entry in self.dsr_ask_catalog.catalog()
            ]
        }

    async def prospecting(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Run account prioritization from an API payload."""
        normalized = self._payload(payload)
        if not normalized.get("account_id") and normalized.get("account") is None:
            return await self._prospect_territory(normalized)
        return await self._run_named(WorkflowIntent.PROSPECTING, payload)

    async def discovery(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Prepare account and competitive discovery context."""
        return await self._run_named(WorkflowIntent.DISCOVERY, payload)

    async def outreach(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Create a concise three-channel outreach sequence."""
        return await self._run_named(WorkflowIntent.OUTREACH, payload)

    async def deal_risk(self, payload: Mapping[str, Any]) -> OrchestrationResult:
        """Assess opportunity hygiene risks."""
        return await self._run_named(WorkflowIntent.DEAL_RISK, payload)

    async def accounts(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Search accounts by name/domain or filter them by territory."""
        normalized = self._payload(payload)
        territory = normalized.get("territory_id") or normalized.get("territory")
        if territory:
            records = await invoke_tool(
                self.sfdc_tool,
                ("get_accounts_by_territory",),
                territory=territory,
            )
        else:
            query = normalized.get("account_id") or normalized.get("message") or ""
            records = await invoke_tool(self.sfdc_tool, ("find",), query=query)
        return {"accounts": [self._serializable(item) for item in (records or [])]}

    async def account_quick_view(self, account_id: str) -> dict[str, Any]:
        """Aggregate the local account sources for a low-latency 360° view."""
        account = next(
            (
                item
                for item in self._all_accounts()
                if str(value(item, "id")) == str(account_id)
            ),
            None,
        )
        if account is None:
            raise ValueError(f"Account '{account_id}' was not found")

        signals, technographics, risk = await self._account_records(account)
        return {
            "account": self._serializable(account),
            "intent": [self._serializable(signal) for signal in signals],
            "technographics": self._serializable(technographics),
            "deal_risk": self._serializable(risk),
        }

    async def territories(self, payload: Mapping[str, Any]) -> dict[str, list[str]]:
        """List known territories from the local Salesforce source."""
        del payload
        repository = getattr(self.sfdc_tool, "_repository", None)
        all_records = repository.all() if repository is not None else []
        return {
            "territories": sorted(
                {
                    str(value(account, "territory"))
                    for account in all_records
                    if value(account, "territory")
                }
            )
        }

    async def _run_named(
        self, intent: WorkflowIntent, payload: Mapping[str, Any]
    ) -> OrchestrationResult:
        normalized = self._payload(payload)
        marker = {
            WorkflowIntent.PROSPECTING: "prioritize prospects",
            WorkflowIntent.DISCOVERY: "prepare discovery",
            WorkflowIntent.OUTREACH: "write outreach",
            WorkflowIntent.DEAL_RISK: "assess deal risk",
            WorkflowIntent.ACCOUNT: "research account",
        }[intent]
        message = f"{marker}: {normalized.get('message') or ''}".strip()
        return await self.run(
            message,
            account_id=normalized.get("account_id"),
            opportunity_id=normalized.get("opportunity_id"),
            context=normalized.get("context"),
        )

    async def _prospect_territory(
        self, payload: Mapping[str, Any]
    ) -> OrchestrationResult:
        """Rank all matching territory accounts by explainable intent score."""
        message = str(payload.get("message") or payload.get("request") or "")
        territory = payload.get("territory_id") or payload.get("territory")
        if not territory:
            match = re.search(r"\b(?:US|EMEA|APAC)[-_ ][A-Z]+\b", message.upper())
            territory = match.group(0).replace("_", "-").replace(" ", "-") if match else None

        if territory:
            accounts = await invoke_tool(
                self.sfdc_tool,
                ("get_accounts_by_territory",),
                territory=str(territory),
            )
        else:
            repository = getattr(self.sfdc_tool, "_repository", None)
            accounts = repository.all() if repository is not None else []

        ranked: list[tuple[Any, Any, Any]] = []
        for account in accounts or []:
            signals = await invoke_tool(
                self.intent_tool,
                ("get_intent_by_domain",),
                domain=value(account, "domain"),
            )
            signal_list = list(signals) if isinstance(signals, (list, tuple)) else [signals]
            signal = next((item for item in signal_list if item is not None), {})
            score = await self.intent_scorer.run(intent=signal, account=account)
            ranked.append((account, signal, score))
        ranked.sort(key=lambda item: item[2].score, reverse=True)

        lines = ["## Territory Prospecting"]
        if territory:
            lines.append(f"**Territory:** {territory}")
        if not ranked:
            lines.append("No matching accounts were found. Try another territory or tier.")
        for index, (account, signal, score) in enumerate(ranked, start=1):
            topics = ", ".join(value(signal, "intent_topics", default=[])) or "No active topics"
            lines.append(
                f"{index}. **{value(account, 'name')}** — {score.score}/100 "
                f"({score.priority}); {topics}"
            )
        return OrchestrationResult(
            intent=WorkflowIntent.PROSPECTING,
            markdown="\n".join(lines),
            data={
                "territory": territory,
                "accounts": [
                    {
                        "account": self._serializable(account),
                        "intent": self._serializable(signal),
                        "score": self._serializable(score),
                    }
                    for account, signal, score in ranked
                ],
            },
        )

    @staticmethod
    def _payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        context = normalized.get("context")
        normalized["context"] = dict(context) if isinstance(context, Mapping) else {}
        return normalized

    @staticmethod
    def _task_board(normalized: Mapping[str, Any]) -> list[Any]:
        """Read the client-owned task lists carried on the request context."""
        context = normalized.get("context") or {}
        board = context.get("tasks") if isinstance(context, Mapping) else None
        return list(board) if isinstance(board, (list, tuple)) else []

    def _all_accounts(self) -> tuple[Any, ...]:
        """Return every account in the local Salesforce source."""
        repository = getattr(self.sfdc_tool, "_repository", None)
        return tuple(repository.all()) if repository is not None else ()

    def _arbitrate_action(self, normalized: Mapping[str, Any], message: str) -> Any:
        """Decide between a menu selection and the action the message asks for.

        A locked action comes from a menu click and always runs. Otherwise a
        selection is only a default: when the typed message matches a catalog
        alias of its own, the typed request wins so that a stale selection can
        never answer a different question.
        """
        requested = normalized.get("action")
        if not requested or normalized.get("action_locked"):
            return requested
        return None if not self.dsr_ask_catalog.classify(message).is_default else requested

    def _with_named_account(self, normalized: dict[str, Any]) -> dict[str, Any]:
        """Prefer an account named in the message over the one selected in the UI."""
        context = dict(normalized.get("context") or {})
        accounts = self._all_accounts()
        account = self._named_account(str(normalized.get("message") or ""), accounts)
        if account is None:
            selected = normalized.get("account") or context.get("account")
            account = self._canonical_account(selected, accounts)
        if account is None and normalized.get("account_id"):
            account = next(
                (
                    item
                    for item in accounts
                    if str(value(item, "id")) == str(normalized["account_id"])
                ),
                None,
            )
        if account is not None:
            context["account"] = account
            normalized["account"] = account
            normalized["account_id"] = str(
                value(account, "id", default=normalized.get("account_id") or "")
            )
        normalized["context"] = context
        return normalized

    @staticmethod
    def _canonical_account(candidate: Any, accounts: Sequence[Any]) -> Any | None:
        """Swap a client-supplied account mapping for its canonical CRM record.

        The dashboard posts the account it has on screen as plain JSON, which
        drops the model properties that deal-risk scoring reads. Matching it back
        to the local record keeps every answer consistent with the CRM source.
        """
        if candidate is None or not isinstance(candidate, Mapping):
            return candidate
        identifier = str(value(candidate, "id", "account_id", default=""))
        match = next(
            (item for item in accounts if identifier and str(value(item, "id")) == identifier),
            None,
        )
        return match or candidate

    @classmethod
    def _named_account(cls, message: str, accounts: Sequence[Any]) -> Any | None:
        """Return the account ``message`` names, matching the longest handle."""
        if not message.strip():
            return None
        haystack = cls._padded(message)
        best: tuple[int, Any] | None = None
        for handle, account in cls._account_handles(accounts):
            padded = cls._padded(handle)
            if padded.strip() and padded in haystack and (best is None or len(padded) > best[0]):
                best = (len(padded), account)
        return best[1] if best is not None else None

    @staticmethod
    def _padded(text: str) -> str:
        """Fold ``text`` to space-padded lowercase words so handles match on edges."""
        folded = "".join(item if item.isalnum() else " " for item in text.lower())
        return f" {' '.join(folded.split())} "

    @staticmethod
    def _account_handles(accounts: Sequence[Any]) -> tuple[tuple[str, Any], ...]:
        """Build the names, domains, and ids that can identify each account.

        A leading word such as "Meridian" also identifies its account, but only
        while no other account starts with the same word.
        """
        handles: list[tuple[str, Any]] = []
        leading: dict[str, list[Any]] = {}
        for account in accounts:
            name = str(value(account, "name", default=""))
            domain = str(value(account, "domain", default=""))
            candidates = (name, domain, domain.split(".")[0], str(value(account, "id", default="")))
            handles += [(token, account) for token in candidates if len(token) >= 4]
            head = name.split(" ", 1)[0]
            if len(head) >= 4:
                leading.setdefault(head.lower(), []).append(account)
        handles += [(head, found[0]) for head, found in leading.items() if len(found) == 1]
        return tuple(handles)

    async def _account_records(self, account: Any) -> tuple[list[Any], Any, Any]:
        """Join the intent signals, technology record, and deal risk for ``account``."""
        domain = str(value(account, "domain", default=""))
        matching = await invoke_tool(
            self.intent_tool,
            ("get_intent_by_domain",),
            domain=domain,
        )
        matches = list(matching) if isinstance(matching, (list, tuple)) else [matching]
        technographics = await invoke_tool(
            self.zoominfo_tool,
            ("get_tech_stack_and_contacts", "get_by_domain"),
            domain=domain,
        )
        risk = await self.deal_risk_agent.run(opportunity=account)
        return [item for item in matches if item is not None], technographics, risk

    def _build_graph(self, intent: WorkflowIntent) -> StateGraph:
        graph = StateGraph().add_node("load_account", self._load_account)
        if intent == WorkflowIntent.DEAL_RISK:
            return (
                StateGraph()
                .add_node("load_opportunity", self._load_opportunity)
                .add_node("assess_risk", self._assess_risk)
                .add_edge("load_opportunity", "assess_risk")
            )
        if intent == WorkflowIntent.PROSPECTING:
            graph.add_parallel(
                {
                    "load_intent": self._load_intent,
                    "build_intel": self._build_intel,
                },
                after="load_account",
            )
            graph.add_node("score_intent", self._score_intent)
            graph.add_edge("load_intent", "score_intent")
            graph.add_edge("load_account", "score_intent")
            return graph
        if intent == WorkflowIntent.DISCOVERY:
            graph.add_node("build_intel", self._build_intel)
            graph.add_node("position", self._position)
            return graph.add_sequence(("load_account", "build_intel", "position"))
        if intent == WorkflowIntent.OUTREACH:
            graph.add_node("build_intel", self._build_intel)
            graph.add_node("position", self._position)
            graph.add_node("draft_outreach", self._draft_outreach)
            return graph.add_sequence(("load_account", "build_intel", "position", "draft_outreach"))
        graph.add_node("build_intel", self._build_intel)
        return graph.add_edge("load_account", "build_intel")

    async def _load_account(self, state: Mapping[str, Any]) -> dict[str, Any]:
        if state.get("account") is not None:
            return {}
        identifier = (
            state.get("account_id")
            or value(state.get("context"), "account_name")
            or state.get("request")
        )
        account = self._account_by_id(identifier)
        if account is None and identifier:
            account = await invoke_tool(
                self.sfdc_tool,
                (
                    "get_account",
                    "get_account_by_name",
                    "fetch_account",
                    "lookup_account",
                    "find",
                    "get",
                ),
                name=identifier,
            )
        if isinstance(account, (list, tuple)):
            account = account[0] if account else None
        if account is None:
            account = self._named_account(str(identifier or ""), self._all_accounts())
        if account is None:
            raise ValueError("An account or configured SFDCTool is required")
        return {"account": account}

    def _account_by_id(self, identifier: Any) -> Any | None:
        """Return the CRM record whose id equals ``identifier``, if any."""
        if identifier is None or identifier == "":
            return None
        return next(
            (
                item
                for item in self._all_accounts()
                if str(value(item, "id")) == str(identifier)
            ),
            None,
        )

    async def _load_opportunity(self, state: Mapping[str, Any]) -> dict[str, Any]:
        if state.get("opportunity") is not None:
            return {}
        repository = getattr(self.sfdc_tool, "_repository", None)
        identifier = state.get("opportunity_id") or state.get("account_id")
        if repository is not None and identifier:
            account = next(
                (
                    item
                    for item in repository.all()
                    if str(value(item, "id")) == str(identifier)
                ),
                None,
            )
            if account is not None:
                return {"opportunity": account}
        opportunity = await invoke_tool(
            self.sfdc_tool,
            ("get_opportunity", "fetch_opportunity", "lookup_opportunity", "get"),
            opportunity_id=state.get("opportunity_id"),
        )
        if opportunity is None:
            raise ValueError("An opportunity or configured SFDCTool is required")
        return {"opportunity": opportunity}

    async def _load_intent(self, state: Mapping[str, Any]) -> dict[str, Any]:
        if state.get("intent") is not None:
            return {}
        signal = await invoke_tool(
            self.intent_tool,
            (
                "get_intent_by_domain",
                "get_intent",
                "get_signals",
                "fetch_intent",
                "search",
            ),
            domain=value(state["account"], "domain"),
        )
        signals = (
            list(signal) if isinstance(signal, (list, tuple)) else ([signal] if signal else [])
        )
        return {"intent": signals[0] if signals else {}, "signals": signals}

    async def _build_intel(self, state: Mapping[str, Any]) -> dict[str, Any]:
        result = await self.account_intel.run(
            account=state["account"],
            contacts=state.get("contacts"),
            technographics=state.get("technographics"),
        )
        return {"account_intel": result}

    async def _score_intent(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "intent_score": await self.intent_scorer.run(
                intent=state.get("intent", {}), account=state["account"]
            )
        }

    async def _position(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intel = state["account_intel"]
        return {
            "competitive_positioning": await self.positioning.run(
                technographics=intel.installed_technology,
                battlecards=state.get("battlecards"),
            )
        }

    async def _draft_outreach(self, state: Mapping[str, Any]) -> dict[str, Any]:
        intel = state["account_intel"]
        contact = intel.decision_makers[0] if intel.decision_makers else None
        signals = state.get("signals") or (
            [state["intent"]] if state.get("intent") is not None else []
        )
        return {
            "outreach": await self.outreach_agent.run(
                account=state["account"],
                contact=contact,
                signals=signals,
                positioning=state.get("competitive_positioning"),
            )
        }

    async def _assess_risk(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return {"deal_risk": await self.deal_risk_agent.run(opportunity=state["opportunity"])}

    def _synthesize(self, intent: WorkflowIntent, state: Mapping[str, Any]) -> str:
        title = intent.value.replace("_", " ").title()
        lines = [f"## {title}"]
        if "intent_score" in state:
            score = state["intent_score"]
            lines += [
                f"- **Priority:** {score.priority.title()} ({score.score}/100)",
                f"- {score.rationale}",
            ]
        if "account_intel" in state:
            intel = state["account_intel"]
            lines.append(f"- **Account:** {intel.summary}")
            if intel.decision_makers:
                lines.append(
                    "- **Start with:** "
                    + ", ".join(
                        f"{person.name} ({person.title})" for person in intel.decision_makers[:3]
                    )
                )
        if "competitive_positioning" in state:
            positioning = state["competitive_positioning"]
            for position in positioning.positions:
                strategy = "; ".join(position.strategy) or "No approved strategy recorded"
                lines.append(f"- **{position.competitor}:** {strategy}")
                if position.landmines:
                    lines.append(f"  - Avoid: {'; '.join(position.landmines)}")
        if "outreach" in state:
            for message in state["outreach"].messages:
                label = message.channel.title()
                subject = f" — {message.subject}" if message.subject else ""
                lines += [f"### {label}{subject}", message.body]
        if "deal_risk" in state:
            risk = state["deal_risk"]
            lines.append(f"- **Risk:** {risk.risk_level.title()} ({risk.risk_score}/100)")
            for flag in risk.flags:
                label = flag.code.replace("_", " ").title()
                lines.append(f"- **{label}:** {flag.evidence} {flag.recommendation}")
        return "\n".join(lines)

    @classmethod
    def _serializable(cls, item: Any) -> Any:
        if isinstance(item, BaseModel):
            return {key: cls._serializable(value_) for key, value_ in model_dump(item).items()}
        if isinstance(item, Mapping):
            return {str(key): cls._serializable(value_) for key, value_ in item.items()}
        if isinstance(item, (list, tuple)):
            return [cls._serializable(value_) for value_ in item]
        if isinstance(item, Enum):
            return item.value
        return item
