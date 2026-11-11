"""Analisis Harga Timpang screening against supplied HPS unit prices."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bidsentry.schemas.comprehensive import BoQLineItem


DEFAULT_HIGH_RATIO = Decimal("1.10")
DEFAULT_LOW_RATIO = Decimal("0.80")


def audit_pricing_imbalance(
    items: list[BoQLineItem],
    *,
    high_ratio: Decimal = DEFAULT_HIGH_RATIO,
    low_ratio: Decimal = DEFAULT_LOW_RATIO,
    source_pages: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Flag prices over the configured HPS band; low prices need no cost note."""
    if high_ratio <= 0 or low_ratio < 0 or low_ratio >= high_ratio:
        raise ValueError("Pricing thresholds must satisfy 0 <= low_ratio < high_ratio.")
    source_pages = source_pages or {}
    findings: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        if item.hps_unit_price is None or item.hps_unit_price <= 0:
            continue
        ratio = item.unit_price_offered / item.hps_unit_price
        has_cost_analysis = bool((item.cost_analysis or "").strip())
        issue = None
        if ratio > high_ratio:
            issue = "HARGA_TIMPANG_HIGH"
        elif ratio < low_ratio and not has_cost_analysis:
            issue = "HARGA_TIMPANG_LOW_NO_COST_ANALYSIS"
        if issue:
            quote = item.source_quote
            citation_page = item.page_ref
            citation_status = "not_provided"
            if quote and citation_page and quote in source_pages.get(citation_page, ""):
                citation_status = "verified_exact_substring"
            elif quote and not citation_page:
                citation_page = next((page_ref for page_ref, text in source_pages.items() if quote in text), None)
                citation_status = "verified_exact_substring" if citation_page else "unverified_quote_omitted"
            elif quote:
                citation_status = "unverified_quote_omitted"
            else:
                quote = None
            findings.append({
                "item_code": item.item_code or f"BOQ-{index:04d}",
                "description": item.description,
                "page_ref": citation_page,
                "citation_page_ref": citation_page,
                "unit_price_offered": _number(item.unit_price_offered),
                "hps_unit_price": _number(item.hps_unit_price),
                "deviation_percentage": round(float((ratio - 1) * 100), 4),
                "cost_analysis_provided": has_cost_analysis,
                "anomaly_type": issue,
                "status": "REVIEW_REQUIRED",
                "source_quote": quote if citation_status == "verified_exact_substring" else None,
                "citation_status": citation_status,
            })
    return {
        "status": "screened" if items else "no_structured_boq_data",
        "high_threshold_ratio": str(high_ratio),
        "low_threshold_ratio": str(low_ratio),
        "finding_count": len(findings),
        "findings": findings,
        "interpretation": "Ambang 110%/80% adalah parameter skrining yang diminta, bukan ambang hukum universal; verifikasi HPS dan analisis biaya terhadap dokumen sumber.",
    }


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)
