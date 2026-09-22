"""Shared output from every JSON-grounded specialist."""

from typing import Literal

from pydantic import BaseModel, Field


class SpecialistReport(BaseModel):
    answer: str = Field(
        default="",
        description="Direct answer to this specialist's part of the request.",
    )
    facts: list[str] = Field(
        default_factory=list,
        description="Specific names, amounts, dates, and evidence from the supplied data.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Useful next steps supported by the supplied data.",
    )
    status: Literal["success", "partial", "error"] = "success"
    error: str = ""
