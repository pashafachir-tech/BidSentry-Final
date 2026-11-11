"""Pydantic response contracts for the HTTP API.

Every route handled by :class:`bidsentry.api.routes.ApiRouter` returns data that
is validated against one of these models before it leaves the server, so a
shape regression fails loudly in tests instead of silently breaking the UI.

Two strictness levels are deliberate:

* Fresh results (``AuditResult``) are strict: findings must be valid
  :class:`~bidsentry.schemas.findings.Finding` objects and the risk must be a
  :class:`~bidsentry.schemas.findings.RiskAssessment`.
* Records read back from the audit log (``AuditRecord`` / ``AuditRow``) are
  lenient, because the log also holds audits written by earlier versions; they
  validate the identifying fields and keep the rest as stored.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bidsentry.schemas.findings import Finding, ProofStep, RiskAssessment


class _Open(BaseModel):
    """Typed core with tolerated extra keys (nested legacy payloads)."""

    model_config = ConfigDict(extra="allow")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ shared
class EngineMode(_Closed):
    mode: Literal["ai_assisted", "local_fallback", "local_only"]
    label: str
    reason: str
    provider_status: str | None = None


class ProofSummary(_Closed):
    steps: int
    by_kind: dict[str, int]
    ai_calls: int
    ai_providers: list[str]
    python_calculations: int


class ExecutiveSummary(_Closed):
    executive_summary: str
    eligibility: str
    critical_administrative_failures: int
    missing_mandatory_documents: int
    potential_financial_exposure_idr: float
    finding_counts: dict[str, int]
    qualification: str


class DocumentRecord(_Open):
    created_at: str | None = None
    document_kind: str | None = None
    filename: str | None = None
    sha256: str | None = None
    role: str | None = None
    findings_included: int | None = None


# ------------------------------------------------------------------ audits
class AuditResult(_Open):
    audit_id: str = Field(min_length=1)
    created_at: str
    package_name: str
    verdict: Literal["GO", "NO-GO", "BELUM CUKUP BUKTI", "TIDAK ADA SYARAT TERBACA"]
    risk_level: Literal["NOT_ASSESSABLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_label: str
    risk: RiskAssessment
    findings: list[Finding]
    executive_summary: ExecutiveSummary
    proof_log: list[ProofStep]
    proof_summary: ProofSummary
    engine_mode: EngineMode
    owner_role: Literal["pokja", "vendor"] | None = None
    summary: dict[str, int]


class AuditRecord(_Open):
    audit_id: str = Field(min_length=1)
    package_name: str | None = None
    verdict: str | None = None
    risk_level: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    proof_log: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[DocumentRecord] = Field(default_factory=list)
    owner_role: str | None = None
    has_source_text: bool = False


class AuditRow(_Open):
    audit_id: str
    package_name: str
    verdict: str
    risk_level: str
    risk_label: str
    owner_role: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)


class AuditList(_Closed):
    audits: list[AuditRow]


class Overview(_Closed):
    dataset_label: str
    total_audits: int
    local_audits_shown: int
    review_required: int
    risk_distribution: dict[str, int]
    local_engine_runtime: dict[str, Any]
    audits: list[AuditRow]
    generated_at: str


class Deleted(_Closed):
    audit_id: str
    deleted: Literal[True]


# ----------------------------------------------------------- proof & risk
class DecisionRule(_Closed):
    rule: str
    condition: str
    level: str
    label: str


class DecisionTable(_Closed):
    method: str
    rules: list[DecisionRule]


class ProofResponse(_Closed):
    audit_id: str | None
    steps: list[dict[str, Any]]
    summary: dict[str, Any]
    risk: dict[str, Any]
    decision_table: list[DecisionRule]
    ai_governance: dict[str, Any]
    documents: list[DocumentRecord]


# ---------------------------------------------------------------- economics
class TokenUsage(_Closed):
    input: int
    output: int
    basis: Literal["measured", "estimated_from_document_length"]
    ai_calls: int


class EconomicsAssumptions(_Closed):
    price_usd_per_1m_input_tokens: float
    price_usd_per_1m_output_tokens: float
    usd_idr_rate: float
    manual_review_hours_per_package: float
    manual_hourly_cost_idr: float
    packages_per_year: int
    price_source: str


class AnnualProjection(_Closed):
    packages: int
    inference_cost_idr: float
    manual_review_cost_idr: float
    manual_hours: float


class EconomicsResponse(_Closed):
    audit_id: str | None
    tokens: TokenUsage
    inference_cost_idr: float
    inference_cost_usd: float
    machine_seconds: float
    manual_review_cost_idr: float
    manual_review_seconds: float
    time_reduction_factor: float | None
    annual: AnnualProjection
    assumptions: EconomicsAssumptions
    caveat: str


# ---------------------------------------------------------------- documents
class DocumentResponse(_Closed):
    filename: str
    content_type: str
    content_base64: str
    draft_only: bool = True
    sha256: str | None = None
    findings_included: list[str | None] | None = None
    source_origin: Literal["audit", "client"] | None = None


class AuditLogIntegrity(_Closed):
    valid: bool
    records: int
    message: str
    sealed: bool


class BoQExportResponse(_Closed):
    filename: str
    content_type: str
    content_base64: str
    line_items: int
    python_mismatches: int
    calculated_subtotal_idr: float


class WorkbookResponse(_Closed):
    filename: str
    content_type: str
    content_base64: str


class ExtractionResponse(_Closed):
    filename: str
    text: str
    characters: int
    extraction_mode: str
    scanned_pdf: bool
    truncated: bool
    warnings: list[str]
    pages: int | None = None
    excel_items_count: int | None = None


# -------------------------------------------------------------- misc routes
class FeedbackSnapshot(_Closed):
    audit_id: str | None
    outcomes: dict[str, dict[str, Any]]
    pilot: dict[str, Any]
    note: str
    reviewed_assessment: RiskAssessment | None = None


class BenchmarkSummary(_Open):
    status: Literal["ok", "not_generated"]
    message: str | None = None
    generated_at: str | None = None
    pooled: dict[str, Any] | None = None
    claim_guidance: str | None = None
    suites: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class DemoPackage(_Closed):
    key: str
    role: Literal["pokja", "vendor"]
    title: str
    story: str
    synthetic: bool
    request: dict[str, Any]


class DemoPackages(_Closed):
    packages: list[DemoPackage]


class Health(_Closed):
    status: Literal["ok"]
    version: str
    engine: str
    integrations: dict[str, Any]


class SessionInfo(_Closed):
    authenticated: bool
    role: Literal["pokja", "vendor"] | None
    label: str | None
    capabilities: list[str]
    roles: list[dict[str, Any]]


__all__ = [
    "AuditList", "AuditRecord", "AuditResult", "AuditRow", "BenchmarkSummary", "BoQExportResponse", "DecisionTable",
    "Deleted", "DemoPackages", "DocumentResponse", "EconomicsResponse", "EngineMode", "ExtractionResponse",
    "FeedbackSnapshot", "Health", "Overview", "ProofResponse", "SessionInfo", "WorkbookResponse",
]
