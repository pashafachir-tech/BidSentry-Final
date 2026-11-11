"""Transparent, deterministic project abandonment risk index."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bidsentry.schemas.comprehensive import DefaultRiskInput


COMPONENT_WEIGHTS = {
    "critical_path_dumping": Decimal("0.45"),
    "financial_capacity_gap": Decimal("0.35"),
    "subcontracting_capacity_gap": Decimal("0.20"),
}


def predict_default_risk(metrics: DefaultRiskInput | dict[str, Any] | None) -> dict[str, Any]:
    """Score only supplied metrics; return unassessed when no signal exists.

    The index is an explainable screening heuristic, not a calibrated default
    probability. Components are normalized to [0, 1] and available components
    are reweighted to sum to one.
    """
    if metrics is None:
        return _unassessed()
    observed = metrics if isinstance(metrics, DefaultRiskInput) else DefaultRiskInput.model_validate(metrics)
    tender = observed.tender_value
    components: dict[str, dict[str, Any]] = {}

    if observed.critical_path_costs:
        severities = []
        for item in observed.critical_path_costs:
            ratio = item.offered_amount / item.estimated_cost_amount
            severity = min(Decimal("1"), max(Decimal("0"), Decimal("1") - ratio))
            severities.append(severity)
        score = max(severities, default=Decimal("0"))
        components["critical_path_dumping"] = {
            "available": True,
            "score": _float(score),
            "item_count": len(severities),
            "basis": "Maximum proportional shortfall of offered amount below supplied estimated cost among supplied critical-path items.",
        }
    else:
        components["critical_path_dumping"] = {"available": False, "score": None, "basis": "No critical-path cost evidence supplied."}

    financial_values = [value for value in (observed.skn_amount, observed.working_capital_amount) if value is not None]
    if financial_values:
        gaps = [min(Decimal("1"), max(Decimal("0"), Decimal("1") - (value / tender))) for value in financial_values]
        components["financial_capacity_gap"] = {
            "available": True,
            "score": _float(sum(gaps) / Decimal(len(gaps))),
            "skn_to_tender_ratio": _ratio(observed.skn_amount, tender),
            "working_capital_to_tender_ratio": _ratio(observed.working_capital_amount, tender),
            "basis": "Mean normalized gap from tender value for the supplied SKN and working-capital amounts.",
        }
    else:
        components["financial_capacity_gap"] = {"available": False, "score": None, "basis": "No SKN or working-capital amount supplied."}

    if observed.subcontracting_commitments is not None and observed.internal_execution_capacity is not None:
        shortfall = max(Decimal("0"), observed.subcontracting_commitments - observed.internal_execution_capacity)
        score = min(Decimal("1"), shortfall / tender)
        components["subcontracting_capacity_gap"] = {
            "available": True,
            "score": _float(score),
            "subcontracting_to_tender_ratio": _ratio(observed.subcontracting_commitments, tender),
            "internal_capacity_to_tender_ratio": _ratio(observed.internal_execution_capacity, tender),
            "basis": "Subcontracting commitments above supplied internal execution capacity, normalized by tender value.",
        }
    else:
        components["subcontracting_capacity_gap"] = {"available": False, "score": None, "basis": "Both subcontracting commitments and internal execution capacity are required."}

    available = [(name, data) for name, data in components.items() if data["available"]]
    if not available:
        return {"status": "unassessed", "project_abandonment_index": None, "components": components, "interpretation": "Insufficient observed inputs; no risk score was inferred."}
    total_weight = sum((COMPONENT_WEIGHTS[name] for name, _ in available), Decimal("0"))
    index = sum((COMPONENT_WEIGHTS[name] * Decimal(str(data["score"])) for name, data in available), Decimal("0")) / total_weight
    return {
        "status": "screening_score",
        "project_abandonment_index": round(_float(index), 6),
        "components": components,
        "weights_used": {name: _float(COMPONENT_WEIGHTS[name] / total_weight) for name, _ in available},
        "interpretation": "Deterministic triage index, not a calibrated probability or a finding of likely abandonment. Validate all source inputs and project-specific context.",
        "umkm_bias_protection": "Sesuai Pasal 65 ayat (4) Perpres 12/2021 dan PP 7/2021, paket usaha kecil (nilai s.d. Rp 15 Miliar) dilindungi dari persyaratan modal korporasi besar. Indeks ini menerapkan normalisasi proporsional non-diskriminatif terhadap skala usaha.",
    }


def _unassessed() -> dict[str, Any]:
    return {"status": "unassessed", "project_abandonment_index": None, "components": {}, "interpretation": "No execution-risk inputs were supplied; no score was inferred."}


def _float(value: Decimal) -> float:
    return float(value)


def _ratio(numerator: Decimal | None, denominator: Decimal) -> float | None:
    return round(float(numerator / denominator), 6) if numerator is not None else None
