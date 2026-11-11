"""Pydantic contracts for contextual structured extraction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ContextExtractionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str = Field(min_length=1, max_length=2000)
    source: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=500)


class ContextualExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str | None = Field(default=None, max_length=1000)
    brand_lockin_signals: list[ContextExtractionItem] = Field(default_factory=list, max_length=100)
    timeline_anomalies: list[ContextExtractionItem] = Field(default_factory=list, max_length=100)
    addendum_changes: list[ContextExtractionItem] = Field(default_factory=list, max_length=100)
    personnel_qualifications: list[ContextExtractionItem] = Field(default_factory=list, max_length=100)
    sla_uptime: list[ContextExtractionItem] = Field(default_factory=list, max_length=100)
