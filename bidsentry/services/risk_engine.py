"""Deterministic verdict and risk-tier decision table.

Risk is expressed as an explicit tier (Rendah / Sedang / Tinggi / Kritis, or
Tidak Dapat Dinilai), never as a 0-100 number. The tier is chosen by the first
rule of the table below that matches; the matched rule and the findings that
triggered it are returned so the UI and the proof log can show *why*.

    R0  no requirement recognised and no finding            -> TIDAK DAPAT DINILAI
    R1  >=1 confirmed GAP on a rule marked critical_on_gap  -> KRITIS
    R2  >=3 confirmed GAP with severity HIGH                -> KRITIS
    R3  >=1 confirmed GAP with severity HIGH                -> TINGGI
    R4  >=1 confirmed GAP (other severities)                -> SEDANG
    R5  >=1 EXPIRING or REVIEW (evidence missing/expiring)  -> SEDANG
    R5b most of a long document matched no rule             -> SEDANG
    R6  otherwise                                           -> RENDAH

The verdict follows the Model Card policy: NO-GO only for confirmed GAPs,
BELUM CUKUP BUKTI for expiring or missing evidence. Findings a human reviewer
marked NOT_SUPPORTED can be excluded to produce a post-review assessment.
Candidates an AI proposed but no rule confirmed are shown to reviewers and never
take part in this table.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bidsentry.evaluators.rule_catalog import CATALOG, canonical_code
from bidsentry.schemas.findings import RiskAssessment, RiskDriver, RiskLevel, Verdict

STATUSES = ("TERPENUHI", "GAP", "EXPIRING", "SUPERSEDED", "REVIEW")

DECISION_TABLE: tuple[tuple[str, str], ...] = (
    ("R0", "Tidak ada persyaratan yang terbaca dan tidak ada temuan"),
    ("R1", "≥1 kesenjangan terkonfirmasi pada aturan berdampak kritis"),
    ("R2", "≥3 kesenjangan terkonfirmasi berkeparahan tinggi"),
    ("R3", "≥1 kesenjangan terkonfirmasi berkeparahan tinggi"),
    ("R4", "≥1 kesenjangan terkonfirmasi berkeparahan sedang/rendah"),
    ("R5", "Ada bukti yang belum lengkap atau dokumen segera kedaluwarsa"),
    ("R5b", "Dokumen panjang tetapi hampir tidak ada klausul yang dikenali aturan"),
    ("R6", "Seluruh persyaratan yang terbaca terpenuhi"),
)


def _is_critical(finding: dict[str, Any]) -> bool:
    rule = CATALOG.get(canonical_code(str(finding.get("id", ""))))
    return bool(rule and rule.critical_on_gap) or finding.get("severity") == "CRITICAL"


def _driver(finding: dict[str, Any], reason: str) -> RiskDriver:
    return RiskDriver(
        finding_id=str(finding.get("id", "")),
        clause=str(finding.get("clause", ""))[:400],
        status=str(finding.get("status", "")),
        severity=str(finding.get("severity", "")),
        reason=reason,
    )


def assess(
    findings: list[dict[str, Any]],
    *,
    requirements_recognized: int,
    excluded_finding_ids: Iterable[str] = (),
    low_coverage: bool = False,
) -> RiskAssessment:
    """Return verdict and risk tier from deterministic findings only."""
    excluded = {str(item) for item in excluded_finding_ids}
    decisive = [item for item in findings if item.get("origin") != "ai_extraction_unconfirmed"]
    active = [item for item in decisive if str(item.get("id")) not in excluded]
    counts = {status: sum(item.get("status") == status for item in active) for status in STATUSES}

    gaps = [item for item in active if item.get("status") == "GAP"]
    critical_gaps = [item for item in gaps if _is_critical(item)]
    high_gaps = [item for item in gaps if item.get("severity") in {"HIGH", "CRITICAL"}]
    pending = [item for item in active if item.get("status") in {"EXPIRING", "REVIEW"}]

    if requirements_recognized == 0 and not decisive:
        level, rule, drivers = RiskLevel.NOT_ASSESSABLE, "R0", []
    elif critical_gaps:
        level, rule = RiskLevel.CRITICAL, "R1"
        drivers = [_driver(item, "Aturan berdampak kritis") for item in critical_gaps]
    elif len(high_gaps) >= 3:
        level, rule = RiskLevel.CRITICAL, "R2"
        drivers = [_driver(item, "Akumulasi kesenjangan tinggi") for item in high_gaps]
    elif high_gaps:
        level, rule = RiskLevel.HIGH, "R3"
        drivers = [_driver(item, "Kesenjangan berkeparahan tinggi") for item in high_gaps]
    elif gaps:
        level, rule = RiskLevel.MEDIUM, "R4"
        drivers = [_driver(item, "Kesenjangan terkonfirmasi") for item in gaps]
    elif pending:
        level, rule = RiskLevel.MEDIUM, "R5"
        drivers = [_driver(item, "Bukti belum lengkap" if item.get("status") == "REVIEW" else "Segera kedaluwarsa") for item in pending]
    elif low_coverage:
        level, rule, drivers = RiskLevel.MEDIUM, "R5b", []
    else:
        level, rule, drivers = RiskLevel.LOW, "R6", []

    if level is RiskLevel.NOT_ASSESSABLE:
        verdict = Verdict.NOT_READABLE
    elif gaps:
        verdict = Verdict.NO_GO
    elif pending or low_coverage:
        verdict = Verdict.INSUFFICIENT_EVIDENCE
    else:
        verdict = Verdict.GO

    rule_text = dict(DECISION_TABLE)[rule]
    if drivers:
        names = ", ".join(driver.finding_id for driver in drivers[:4])
        more = f" dan {len(drivers) - 4} lainnya" if len(drivers) > 4 else ""
        rationale = f"Risiko {level.label}: {rule_text} ({names}{more})."
    elif level is RiskLevel.NOT_ASSESSABLE:
        rationale = "Tidak Dapat Dinilai: dokumen tidak memuat persyaratan yang dikenali mesin (mungkin pindaian tanpa OCR). Ini bukan tanda aman."
    else:
        rationale = f"Risiko {level.label}: {rule_text}."

    return RiskAssessment(
        level=level,
        label=level.label,
        color=level.color,
        rank=level.rank,
        verdict=verdict,
        rule_applied=rule,
        rationale=rationale,
        drivers=drivers[:8],
        counts=counts,
        excluded_by_reviewer=sorted(excluded & {str(item.get("id")) for item in findings}),
    )


def decision_table() -> list[dict[str, str]]:
    """Expose the table so the UI and docs render the exact same rules."""
    levels = {"R0": "NOT_ASSESSABLE", "R1": "CRITICAL", "R2": "CRITICAL", "R3": "HIGH", "R4": "MEDIUM", "R5": "MEDIUM", "R5b": "MEDIUM", "R6": "LOW"}
    return [{"rule": rule, "condition": text, "level": levels[rule], "label": RiskLevel(levels[rule]).label} for rule, text in DECISION_TABLE]


__all__ = ["DECISION_TABLE", "assess", "decision_table"]
