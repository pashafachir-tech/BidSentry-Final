"""Pydantic v2 contracts for the comprehensive audit API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator



class StrictModel(BaseModel):
    # Preserve source page text and quote bytes exactly for grounding checks.
    model_config = ConfigDict(extra="forbid")


class PageChunk(StrictModel):
    page_ref: str = Field(min_length=1, max_length=120)
    text: str = Field(max_length=2_000_000)


class BoQLineItem(StrictModel):
    item_code: str | None = Field(default=None, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    volume: Decimal = Field(ge=0)
    unit: str = Field(min_length=1, max_length=80)
    unit_price_offered: Decimal = Field(ge=0)
    total_offered: Decimal = Field(ge=0)
    hps_unit_price: Decimal | None = Field(default=None, ge=0)
    source_quote: str | None = Field(default=None, max_length=4000)
    page_ref: str | None = Field(default=None, max_length=120)
    cost_analysis: str | None = Field(default=None, max_length=4000)


class CriticalPathCost(StrictModel):
    item_code: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    offered_amount: Decimal = Field(ge=0)
    estimated_cost_amount: Decimal = Field(gt=0)


class DefaultRiskInput(StrictModel):
    """Observed inputs; omitted metrics remain explicitly unassessed."""

    tender_value: Decimal = Field(gt=0)
    critical_path_costs: list[CriticalPathCost] = Field(default_factory=list, max_length=5000)
    skn_amount: Decimal | None = Field(default=None, ge=0)
    working_capital_amount: Decimal | None = Field(default=None, ge=0)
    subcontracting_commitments: Decimal | None = Field(default=None, ge=0)
    internal_execution_capacity: Decimal | None = Field(default=None, ge=0)

    @field_validator("critical_path_costs")
    @classmethod
    def unique_item_codes(cls, value: list[CriticalPathCost]) -> list[CriticalPathCost]:
        codes = [item.item_code for item in value]
        if len(codes) != len(set(codes)):
            raise ValueError("critical_path_costs item_code values must be unique")
        return value


class VendorEvidence(StrictModel):
    vendor_id: str = Field(min_length=1, max_length=120)
    vendor_name: str = Field(min_length=1, max_length=240)
    submission_timestamp: datetime | None = None
    pdf_base64: str | None = Field(default=None, max_length=12_000_000)
    document_chunks: list[PageChunk] = Field(default_factory=list, max_length=2000)
    document_metadata: dict[str, Any] | None = None
    entities: dict[str, Any] = Field(default_factory=dict, max_length=100)
    technical_proposal_text: str = Field(default="", max_length=2_000_000)
    contract_text: str = Field(default="", max_length=2_000_000)
    embedding: list[float] | None = Field(default=None, max_length=8192)
    boq_items: list[BoQLineItem] = Field(default_factory=list, max_length=20_000)


class ArtifactSignal(StrictModel):
    artifact_type: Literal["SIGNATURE", "STAMP", "E_METERAI"]
    page_ref: str | None = Field(default=None, max_length=120)
    detected: bool | None = None
    alpha_layer: bool | None = None
    vector_paths: bool | None = None
    dpi: int | None = Field(default=None, ge=1, le=100_000)
    certified_signature: bool | None = None
    description: str = Field(default="", max_length=2000)


class CandidateEvaluation(StrictModel):
    clause_id: str = Field(min_length=1, max_length=120)
    requirement: str = Field(min_length=1, max_length=2000)
    status: Literal["POTENTIAL_MATCH", "POTENTIAL_GAP", "NOT_FOUND", "UNVERIFIED"]
    verbatim_quote: str | None = Field(default=None, max_length=4000)
    page_ref: str | None = Field(default=None, max_length=120)
    confidence: float = Field(default=0.5, ge=0, le=1)
    risk_note: str = Field(default="", max_length=2000)

class ComprehensiveAuditRequest(StrictModel):
    tender_id: str = Field(min_length=1, max_length=120)
    vendor_id: str = Field(min_length=1, max_length=120)
    vendor_name: str = Field(min_length=1, max_length=240)
    submission_timestamp: datetime | None = None
    document_metadata: dict[str, Any] | None = None
    entities: dict[str, Any] = Field(default_factory=dict, max_length=100)
    tender_regulations_and_hps: str = Field(default="", max_length=2_000_000)
    document_chunks: list[PageChunk] = Field(default_factory=list, max_length=2000)
    pdf_base64: str | None = Field(default=None, max_length=12_000_000)
    technical_proposal_text: str = Field(default="", max_length=2_000_000)
    contract_text: str = Field(default="", max_length=2_000_000)
    embedding: list[float] | None = Field(default=None, max_length=8192)
    boq_items: list[BoQLineItem] = Field(default_factory=list, max_length=20_000)
    offered_total_price: Decimal | None = Field(default=None, ge=0)
    hps_total_price: Decimal | None = Field(default=None, ge=0)
    vendor_submissions: list[VendorEvidence] = Field(default_factory=list, max_length=100)
    default_risk_metrics: DefaultRiskInput | None = None
    baseline_contract_text: str = Field(default="", max_length=2_000_000)
    artifact_signals: list[ArtifactSignal] = Field(default_factory=list, max_length=500)
    candidate_evaluations: list[CandidateEvaluation] = Field(default_factory=list, max_length=5000)
    allow_external_processing: bool = False
    scoring_weights: dict[str, Decimal] = Field(default_factory=dict)

    @field_validator("scoring_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        if len(value) > 100 or any(weight < 0 for weight in value.values()):
            raise ValueError("Scoring weights must be non-negative and contain at most 100 entries.")
        return value

    @model_validator(mode="after")
    def require_documents_or_file(self) -> "ComprehensiveAuditRequest":
        if not self.document_chunks and not self.pdf_base64:
            raise ValueError("Provide document_chunks or pdf_base64 for a grounded audit.")
        if self.vendor_submissions and len({v.vendor_id for v in self.vendor_submissions}) != len(self.vendor_submissions):
            raise ValueError("vendor_submissions must have unique vendor_id values.")
        return self


class GroundedFinding(StrictModel):
    clause_id: str
    requirement: str
    status: Literal["POTENTIAL_MATCH", "POTENTIAL_GAP", "NOT_FOUND", "UNVERIFIED", "UNVERIFIED_HALLUCINATION"]
    verbatim_quote: str | None
    page_ref: str | None
    confidence: float = Field(ge=0, le=1)
    risk_note: str = ""


class ExecutiveVerdict(StrictModel):
    status: Literal["REVIEW_REQUIRED"]
    composite_compliance_score: float | None
    risk_level: Literal["LOW", "ELEVATED", "CRITICAL", "UNASSESSED"]
    primary_disqualification_reason: str | None
    automatic_disqualification: bool
    reviewer_note: str


class ComprehensiveModules(StrictModel):
    module_1_document_metadata_forensics: dict[str, Any]
    module_2_financial_and_boq_audit: dict[str, Any]
    module_3_grounded_evaluation: dict[str, Any]
    module_4_bid_rigging_and_contract_dilution: dict[str, Any]
    module_5_artifact_and_signature_verification: dict[str, Any]
    module_6_immutable_audit_trail: dict[str, Any]
    module_7_pdf_sandbox_defense: dict[str, Any]
    module_8_entity_network_graph: dict[str, Any]
    module_9_execution_risk_forecast: dict[str, Any]
    module_10_statutory_mapping: dict[str, Any]
    ai_governance_metadata: dict[str, Any] = Field(default_factory=dict)


class TamperEvidentTrail(StrictModel):
    sequence: int = Field(ge=1)
    previous_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extracted_quotes_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scoring_weights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chain_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification: Literal["hash_chain_recorded"]
    tamper_evident: bool
    non_repudiation_guaranteed: Literal[False]
    limitation: str
    chain_valid_after_append: bool
    records_checked: int = Field(ge=1)


class ComprehensiveAuditResponse(StrictModel):
    audit_run_id: str
    tender_metadata: dict[str, Any]
    executive_verdict: ExecutiveVerdict
    modules: ComprehensiveModules
    tamper_evident_audit_trail: TamperEvidentTrail
