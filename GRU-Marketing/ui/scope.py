"""Cheap, local gate so off-topic chat never reaches Gemini.

The marketing orchestrator is a full LLM hop even when it only says "that's
not my job". This module answers that class of request from a canned string
instead, which costs zero model tokens.

The check is commutative in the same sense as the filter rail: order of
signals does not matter. A known task, an in-scope phrase, or a short
follow-up after an in-scope turn is enough. There is no transitivity claim —
a marketing word in one turn does not license an unrelated later turn.
"""

from __future__ import annotations

import re

from ui.catalog import TASK_MENU

OFF_TOPIC_REPLY = (
    "I only handle marketing work in this workspace — campaigns, content, "
    "events, brand, pipeline analysis, and marketing ops. Pick a task on the "
    "left, or rephrase this as a marketing request."
)

# Small talk is not off-topic. Refusing "hello" makes the workspace read like a
# form rather than an assistant, so the openers that carry a conversation get a
# real answer -- still without spending a model call on them.
GREETING_REPLY = (
    "Hi — James here. I can help with campaigns, content, events, brand, "
    "pipeline, and marketing ops. Pick a task, or just tell me what you need."
)

WELLBEING_REPLY = (
    "Doing well, thanks for asking — and ready when you are. Ask me about "
    "campaigns, content, events, brand, pipeline analysis, or marketing ops."
)

THANKS_REPLY = "Anytime. What should I pick up next?"

ACK_REPLY = (
    "Got it. Tell me what you would like next, or pick a task on the left."
)

CAPABILITY_REPLY = (
    "I am James. Seven teams sit behind me:\n\n"
    "·  Campaign Design — ideas, briefs, competitive messaging\n"
    "·  ABM — account tiering, intel, plays for email, LinkedIn and Folloze\n"
    "·  Content — anchor assets, translations, channel grids\n"
    "·  Brand — sentiment, share of voice, rapid response\n"
    "·  Analysis — campaign performance, pipeline health, decks\n"
    "·  Regional Events — where to run one, who to invite, account briefs\n"
    "·  Marketing Ops — Salesforce campaigns, 6sense segments, list loads\n\n"
    "Every figure comes from our own data and is worked out in code, so you "
    "can check it. Pick a task, or ask in your own words."
)

GOODBYE_REPLY = (
    "Talk soon. This chat stays in the workspace, so you can pick it up again."
)

# Phrases first so "share of voice" is not reduced to the generic word "share".
_SCOPE_PHRASES: tuple[str, ...] = (
    "6sense",
    "salesforce",
    "marketo",
    "share of voice",
    "zero trust",
    "demand council",
    "pipeline coverage",
    "cost per opportunity",
    "campaign brief",
    "generate a ppt",
    "powerpoint",
    "asset grid",
    "list load",
    "field event",
    "paid social",
    "paid search",
    "content syndication",
    "email nurture",
)

_ACCOUNT_ID = re.compile(r"\bacc-\d+\b", re.I)

_SCOPE_WORDS: frozenset[str] = frozenset(
    {
        "campaign",
        "campaigns",
        "pipeline",
        "marketo",
        "salesforce",
        "sfdc",
        "mql",
        "mqls",
        "sqls",
        "lead",
        "leads",
        "segment",
        "segments",
        "event",
        "events",
        "roundtable",
        "webinar",
        "brief",
        "briefs",
        "asset",
        "assets",
        "content",
        "brand",
        "sentiment",
        "abm",
        "attendee",
        "attendees",
        "invite",
        "invitation",
        "deck",
        "ppt",
        "pptx",
        "budget",
        "spend",
        "mops",
        "ops",
        "nurture",
        "syndication",
        "tradeshow",
        "emea",
        "amer",
        "apj",
        "ciso",
        "jasper",
        "folloze",
        "linkedin",
        "messaging",
        "ideation",
        "translate",
        "translation",
        "whitepaper",
        "brochure",
        "checklist",
        "webinars",
        "performance",
        "coverage",
        "stalled",
        "quota",
        "arr",
        "opportunity",
        "opportunities",
        "account",
        "accounts",
    }
)

_OFF_TOPIC_PHRASES: tuple[str, ...] = (
    "capital of",
    "write a poem",
    "write a joke",
    "tell me a joke",
    "what is the weather",
    "how's the weather",
    "recipe for",
    "sports score",
)

_OFF_TOPIC_WORDS: frozenset[str] = frozenset(
    {
        "weather",
        "recipe",
        "pokemon",
        "calculus",
        "homework",
        "linux",
        "kubernetes",
        "bitcoin",
        "cryptocurrency",
        "football",
        "cricket",
        "movie",
        "netflix",
        "poem",
        "joke",
        "riddle",
    }
)

_FOLLOW_UP = re.compile(
    r"^(and|also|plus|same|additionally|what about|how about|for that|"
    r"for those|for them|for it|ditto)\b",
    re.IGNORECASE,
)

_WORD = re.compile(r"[a-z0-9]+")

_KNOWN_TASKS = {item["id"] for group in TASK_MENU for item in group["items"]}

_STOPWORDS = frozenset(
    {
        "what",
        "this",
        "that",
        "with",
        "from",
        "into",
        "next",
        "more",
        "than",
        "should",
        "where",
        "which",
        "about",
        "have",
        "your",
        "their",
        "them",
        "then",
        "when",
        "will",
        "just",
        "make",
        "tell",
        "come",
        "each",
        "into",
        "over",
        "also",
        "does",
        "doing",
        "done",
        "here",
        "there",
        "some",
        "such",
        "only",
        "into",
        "need",
        "needs",
        "want",
        "week",
        "month",
        "year",
        "quarter",
    }
)

_PROMPT_WORDS = {
    token
    for group in TASK_MENU
    for item in group["items"]
    for blob in (item["label"], item["default_prompt"])
    for token in _WORD.findall(str(blob).lower())
    if len(token) >= 4 and token not in _STOPWORDS
}
_SCOPE_WORDS = frozenset(w for w in (_SCOPE_WORDS | _PROMPT_WORDS) if w not in _STOPWORDS)


_PUNCTUATION = re.compile(r"[^a-z0-9' ]+")

# Ordered: the first match wins, so "thanks" is thanks rather than an
# acknowledgment, and the loose acknowledgment pattern is checked last.
_SOCIAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"^(?:how are you(?: doing)?|how'?s it going|how do you do|"
            r"what'?s up|you good|hope you'?re well)$"
        ),
        WELLBEING_REPLY,
    ),
    (
        re.compile(
            r"^(?:who are you|what are you|what can you do|what do you do|"
            r"what can i ask(?: you)?|what should i ask(?: you)?|"
            r"what are your capabilities|how do you work|what is this|"
            r"help|help me)$"
        ),
        CAPABILITY_REPLY,
    ),
    (
        re.compile(
            r"^(?:thanks|thank you|thanx|thx|ty|cheers|many thanks|"
            r"much appreciated|appreciate it)"
            r"(?: james| a lot| so much| very much| again)?$"
        ),
        THANKS_REPLY,
    ),
    (
        re.compile(
            r"^(?:bye|goodbye|good bye|see you|see ya|catch you later|"
            r"good ?night|that'?s all|that is all)"
            r"(?: james| then| for now)?$"
        ),
        GOODBYE_REPLY,
    ),
    (
        re.compile(
            r"^(?:hi|hello|hey|heya|hiya|yo|howdy|greetings|"
            r"good morning|good afternoon|good evening|good day|"
            r"morning|afternoon|evening)"
            r"(?: there| james| team| all| everyone| again)?$"
        ),
        GREETING_REPLY,
    ),
    (
        re.compile(
            r"^(?:ok|okay|alright|all right)? ?"
            r"(?:cool|nice|great|awesome|perfect|excellent|brilliant|"
            r"got it|understood|sounds good|makes sense|no worries|noted|"
            r"fair enough|thanks|thank you)"
            r"(?: thanks| thank you| then)?$"
        ),
        ACK_REPLY,
    ),
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _social_key(text: str) -> str:
    """Lowercase, drop punctuation, collapse spaces. "Hi, James!" -> "hi james"."""
    return _normalise(_PUNCTUATION.sub(" ", _normalise(text)))


def looks_off_topic(text: str) -> bool:
    lowered = _normalise(text)
    if any(phrase in lowered for phrase in _OFF_TOPIC_PHRASES):
        return True
    tokens = set(_WORD.findall(lowered))
    return bool(tokens & _OFF_TOPIC_WORDS)


def looks_in_scope(text: str) -> bool:
    lowered = _normalise(text)
    if any(phrase in lowered for phrase in _SCOPE_PHRASES):
        return True
    if _ACCOUNT_ID.search(lowered):
        return True
    tokens = set(_WORD.findall(lowered))
    return bool(tokens & _SCOPE_WORDS)


def looks_like_follow_up(text: str) -> bool:
    lowered = _normalise(text)
    if not lowered:
        return False
    if _FOLLOW_UP.search(lowered):
        return True
    return len(_WORD.findall(lowered)) <= 6 and not looks_off_topic(text)


def social_reply(text: str) -> str | None:
    """Return a canned conversational answer, or None if this is real work.

    Marketing wins every tie: "hi, how is pipeline looking" is a request with a
    greeting bolted on, not small talk, so anything carrying marketing or
    off-topic vocabulary falls through to the usual gate. Bare affirmatives
    ("ok", "yes") are deliberately not matched either — they are far more often
    an answer to a clarifying question than the end of a conversation.
    """
    cleaned = _social_key(text)
    if not cleaned or looks_in_scope(cleaned) or looks_off_topic(cleaned):
        return None
    for pattern, reply in _SOCIAL_PATTERNS:
        if pattern.match(cleaned):
            return reply
    return None


def is_in_scope(
    message: str,
    *,
    task_id: str = "",
    has_attachments: bool = False,
    has_filters: bool = False,
    previous_turn_in_scope: bool = False,
) -> bool:
    """Return True when the request is cheap to refuse without a model call.

    A selected task id is not enough on its own: the user may have picked a
    task then replaced the draft with an unrelated question. The composed
    default prompt still passes because it contains marketing vocabulary.

    A ticked filter is different. The campaign, event or account is the
    subject of the sentence, so "tell me more about" with a campaign selected
    is a marketing request whose nouns happen to live in the rail rather than
    in the text. Off-topic wording still loses, because that check runs first.
    """
    if looks_off_topic(message):
        lowered = _normalise(message)
        return any(phrase in lowered for phrase in _SCOPE_PHRASES)
    if looks_in_scope(message):
        return True
    if has_attachments or has_filters:
        return True
    if previous_turn_in_scope and looks_like_follow_up(message):
        return True
    return False
