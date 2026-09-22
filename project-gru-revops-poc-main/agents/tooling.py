"""ADK "tool" decorator shim and shared mock-tool result helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from agents.data.crm import list_accounts, resolve_account

F = TypeVar("F", bound=Callable[..., object])

try:
    from google.adk.tools import tool as tool
except ImportError:

    def tool(func: F) -> F:
        """Mark a callable as an ADK tool when the real decorator is unavailable."""
        return func


def error(message: str) -> dict[str, Any]:
    return {"status": "error", "message": message, "data": None}


def success(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "data": data}


def require_account(account_name: str) -> tuple[str | None, dict[str, Any] | None]:
    canonical = resolve_account(account_name)
    if canonical is None:
        return None, error(
            f"Account '{account_name}' was not found. "
            f"Known accounts: {', '.join(list_accounts())}."
        )
    return canonical, None
