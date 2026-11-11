"""Strict supplemental contracts for forensic and execution-risk modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bidsentry.schemas.comprehensive import (
    ArtifactSignal,
    BoQLineItem,
    CandidateEvaluation,
    ComprehensiveAuditRequest,
    ComprehensiveAuditResponse,
    CriticalPathCost,
    DefaultRiskInput,
    GroundedFinding,
    PageChunk,
    VendorEvidence,
)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class EntityEvidence(StrictContract):
    """Typed shell accepted by graph builders; keys remain specific to entity type."""

    values: dict[str, Any] = Field(default_factory=dict, max_length=100)


class DocumentAnomaly(StrictContract):
    anomaly_type: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    page_ref: str | None = Field(default=None, max_length=120)
    source_quote: str | None = Field(default=None, max_length=4000)
    evidence_id: str | None = Field(default=None, max_length=120)
    details: dict[str, Any] = Field(default_factory=dict, max_length=100)


class ClarificationDocumentRequest(StrictContract):
    tender_id: str = Field(min_length=1, max_length=200)
    vendor_name: str = Field(min_length=1, max_length=240)
    format: Literal["docx", "pdf", "markdown", "html"] = "docx"
    anomalies: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class MinutesEvaluationDocumentRequest(StrictContract):
    tender_id: str = Field(min_length=1, max_length=200)
    vendor_name: str = Field(min_length=1, max_length=240)
    format: Literal["docx", "pdf", "markdown", "html"] = "docx"
    findings: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
    legal_mappings: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)


class GroundedProviderResponse(StrictContract):
    findings: list[CandidateEvaluation] = Field(max_length=5000)


class AuditJobError(StrictContract):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1000)


class AuditJobStatus(StrictContract):
    job_id: str = Field(min_length=1, max_length=36)
    tender_id: str = Field(min_length=1, max_length=120)
    vendor_id: str = Field(min_length=1, max_length=120)
    status: Literal["queued", "running", "complete", "failed"]
    progress: int = Field(ge=0, le=100)
    stage: str = Field(min_length=1, max_length=80)
    result: dict[str, Any] | None = None
    error: AuditJobError | None = None
    created_at: datetime
    updated_at: datetime


class AuditJobCreated(StrictContract):
    job_id: str = Field(min_length=1, max_length=36)
    status: Literal["queued"] = "queued"
    status_url: str
    stream_url: str


# Keep one canonical import location for consumers that use the comprehensive API.
__all__ = [
    "ArtifactSignal", "BoQLineItem", "CandidateEvaluation", "ComprehensiveAuditRequest",
    "ComprehensiveAuditResponse", "ClarificationDocumentRequest", "CriticalPathCost", "DefaultRiskInput", "DocumentAnomaly",
    "EntityEvidence", "GroundedFinding", "PageChunk", "VendorEvidence",
    "GroundedProviderResponse", "MinutesEvaluationDocumentRequest", "AuditJobCreated",
    "AuditJobError", "AuditJobStatus",
]
