"""Pass the specialist markdown through to the UI, with paste-ready artifacts."""

from __future__ import annotations

import re

_NAMED_ARTIFACT = re.compile(
    r"###\s+(.+?)(?:\s+·\s+(email|merge_instruction|talking_points|ask|work_order|other))?"
    r"\s*\n```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)```"
)
_FENCE = re.compile(r"```(?:[a-zA-Z0-9_-]*)\n([\s\S]*?)```")
_LOOSE_EMAIL = re.compile(
    r"(?im)^Subject:\s[^\n]+\n[\s\S]*?\nBest regards,?"
)


def _looks_like_email(text: str) -> bool:
    value = text.strip()
    return bool(
        re.search(r"^(subject\s*:|hi\s+\w+)", value, re.I)
        and re.search(r"best regards", value, re.I)
    )


def _email_title(body: str) -> str:
    match = re.search(r"^Subject:\s*(.+)$", body, re.I | re.M)
    if match:
        return match.group(1).strip()[:80] or "Sendable email"
    return "Sendable email"


def parse_artifacts(text: str) -> list[dict[str, str]]:
    """Pull fenced paste-ready blocks, including sendable emails, out of a reply."""
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(title: str, kind: str, body: str) -> None:
        cleaned = body.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        items.append({"title": title.strip() or "Untitled", "kind": kind, "body": cleaned})

    for match in _NAMED_ARTIFACT.finditer(text):
        kind = match.group(2) or ("email" if _looks_like_email(match.group(3)) else "other")
        add(match.group(1), kind, match.group(3))
    for match in _FENCE.finditer(text):
        body = match.group(1).strip()
        if _looks_like_email(body):
            add(_email_title(body), "email", body)
    if not items:
        for match in _LOOSE_EMAIL.finditer(text):
            body = match.group(0).strip()
            if _looks_like_email(body):
                add(_email_title(body), "email", body)
    return items


def parse_reply(text: str) -> dict:
    """Turn orchestrator markdown into a UI payload."""
    cleaned = text.strip()
    payload: dict = {"kind": "plain", "text": cleaned}
    artifacts = parse_artifacts(cleaned)
    if artifacts:
        payload["artifacts"] = artifacts
    return payload
