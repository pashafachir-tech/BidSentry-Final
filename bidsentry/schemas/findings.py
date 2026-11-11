"""Canonical finding, risk and proof-log contracts shared by engine, API and UI.

These models are the single source of truth for the shape of an evaluation
finding. Generators (Berita Acara, sanggahan, workbook) and the frontend consume
the serialized form, so every producer must go through :class:`Finding`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FindingStatus(str, Enum):
    TERPENUHI = "TERPENUHI"     # requirement satisfied by supplied evidence
    GAP = "GAP"                 # confirmed gap / red flag read from the text
    EXPIRING = "EXPIRING"       # credential valid but expires within the warning window
    SUPERSEDED = "SUPERSEDED"   # requirement changed by an addendum
    REVIEW = "REVIEW"           # evidence missing or unreadable; human must check

    @property
    def label(self) -> str:
        return {
            "TERPENUHI": "Terpenuhi",
            "GAP": "Kesenjangan",
            "EXPIRING": "Segera berakhir",
            "SUPERSEDED": "Diubah adendum",
            "REVIEW": "Perlu diperiksa",
        }[self.value]


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskLevel(str, Enum):
    """Explicit, human-readable risk tier. Never expressed as a 0-100 number."""

    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def label(self) -> str:
        return {
            "NOT_ASSESSABLE": "Tidak Dapat Dinilai",
            "LOW": "Rendah",
            "MEDIUM": "Sedang",
            "HIGH": "Tinggi",
            "CRITICAL": "Kritis",
        }[self.value]

    @property
    def rank(self) -> int:
        """Ordinal used only for sorting; not displayed as a score."""
        return {"NOT_ASSESSABLE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}[self.value]

    @property
    def color(self) -> str:
        return {
            "NOT_ASSESSABLE": "gray",
            "LOW": "green",
            "MEDIUM": "amber",
            "HIGH": "orange",
            "CRITICAL": "red",
        }[self.value]


class Verdict(str, Enum):
    GO = "GO"
    NO_GO = "NO-GO"
    INSUFFICIENT_EVIDENCE = "BELUM CUKUP BUKTI"
    NOT_READABLE = "TIDAK ADA SYARAT TERBACA"


Party = Literal["tender_document", "bidder_evidence"]
Origin = Literal["deterministic_rule", "ai_extraction_python_validated", "ai_extraction_unconfirmed"]


class Finding(BaseModel):
    """One evaluated requirement or red flag, with verbatim evidence."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(min_length=1, max_length=80)
    rule_family: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    clause: str = Field(min_length=1, max_length=400)
    status: FindingStatus
    severity: Severity
    party: Party
    objectionable: bool = Field(description="Eligible for a vendor objection letter (tender-document gap only).")
    source: str = Field(default="Dokumen pemilihan", max_length=240)
    requirement_evidence: str | None = Field(default=None, max_length=4000)
    evidence_source: str = Field(default="Bukti belum ditemukan", max_length=240)
    evidence: str = Field(default="", max_length=4000)
    review_note: str = Field(default="", max_length=4000)
    legal_reference: str = Field(default="", max_length=1200)
    legal_verification: Literal["DIPERIKSA_NASKAH", "DIPERIKSA_SEKUNDER", "PERLU_VERIFIKASI_HUKUM"] = "PERLU_VERIFIKASI_HUKUM"
    legal_basis: list[dict[str, str]] = Field(default_factory=list, max_length=10)
    origin: Origin = "deterministic_rule"
    calculation_ref: str | None = Field(default=None, max_length=80, description="Proof-log step id holding the arithmetic.")
    threshold_unverified: bool = Field(default=False, description="Raised by a numeric threshold not yet confirmed in regulation text, so it asks for review instead of a NO-GO.")


class RiskDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_id: str
    clause: str
    status: str
    severity: str
    reason: str


class RiskAssessment(BaseModel):
    """Output of the deterministic risk decision table."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    level: RiskLevel
    label: str
    color: str
    rank: int
    verdict: Verdict
    rule_applied: str
    rationale: str
    method: str = "decision-table-v2"
    drivers: list[RiskDriver] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    excluded_by_reviewer: list[str] = Field(default_factory=list)


ProofKind = Literal[
    "input",
    "pii_redaction",
    "ai_call",
    "ai_validation",
    "calculation",
    "decision",
    "document",
    "guardrail",
]


class ProofStep(BaseModel):
    """One auditable step: what went in, what came out, and how long it took."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    sequence: int
    kind: ProofKind
    title: str
    actor: str = Field(description="Component that executed the step, e.g. 'python:penalty_calculator' or 'watsonx:mistralai/…'.")
    status: Literal["ok", "skipped", "failed", "rejected"] = "ok"
    duration_ms: float | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    formula: str | None = None
    note: str | None = None
    recorded_at: str


__all__ = [
    "Finding",
    "FindingStatus",
    "Origin",
    "Party",
    "ProofKind",
    "ProofStep",
    "RiskAssessment",
    "RiskDriver",
    "RiskLevel",
    "Severity",
    "Verdict",
]
