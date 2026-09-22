"""Structured outputs from RevOps specialists."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RevopsForecastOutput(BaseModel):
    geo: str = ""
    boat: str = ""
    commit_total: int = 0
    upside_total: int = 0
    coverage: int = 0
    missing_data: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class RevopsQuotingOutput(BaseModel):
    quotes: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    bundles: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class RevopsReportingOutput(BaseModel):
    report_type: str = ""
    slides: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class RevopsHygieneOutput(BaseModel):
    accounts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class RevopsOtcOutput(BaseModel):
    accounts: list[str] = Field(default_factory=list)
    arr_total: int = 0
    headroom_total: int = 0
    holds: list[str] = Field(default_factory=list)
    lines: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""


class RevopsPricingOutput(BaseModel):
    account: str = ""
    sku: str = ""
    waterfall: list[str] = Field(default_factory=list)
    below_floor: bool = False
    peer_band: str = ""
    findings: list[str] = Field(default_factory=list)
    records: dict[str, Any] = Field(default_factory=dict)
    topic: str = ""
    next_action: str = ""
    copy_ready: list[str] = Field(default_factory=list)
    reply: str = Field(
        default="",
        description="AE-facing markdown. Choose the structure that fits the ask.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""
