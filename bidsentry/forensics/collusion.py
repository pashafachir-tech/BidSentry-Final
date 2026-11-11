"""Pairwise text and supplied-embedding similarity screening."""

from __future__ import annotations

import math
import re
from typing import Any


_WORD = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
_CONTRACT_TOPICS: dict[str, tuple[str, ...]] = {
    "LIQUIDATED_DAMAGES": ("denda", "keterlambatan", "liquidated damages", "late delivery"),
    "SLA_REMEDIES": ("sla", "service level", "service credit", "penalti layanan", "sanksi layanan"),
    "TERMINATION": ("pemutusan", "pengakhiran", "termination", "terminate", "wanprestasi"),
}
_WEAKENING_TERMS = ("batas maksimum", "maksimum", "setinggi-tingginya", "dibatasi", "cap", "sole remedy", "exclusive remedy")


def compare_proposals(vendors: list[dict[str, Any]], minimum_tokens: int = 100) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    for index, first in enumerate(vendors):
        for second in vendors[index + 1:]:
            text_a = str(first.get("technical_proposal_text", "") or "")
            text_b = str(second.get("technical_proposal_text", "") or "")
            tokens_a = _tokens(text_a)
            tokens_b = _tokens(text_b)
            ngrams_a, ngrams_b = _ngrams(tokens_a), _ngrams(tokens_b)
            union = ngrams_a | ngrams_b
            intersection = ngrams_a & ngrams_b
            jaccard = len(intersection) / len(union) if union else 0.0
            containment = len(intersection) / min(len(ngrams_a), len(ngrams_b)) if ngrams_a and ngrams_b else 0.0
            vector_score = _cosine(first.get("embedding"), second.get("embedding"))
            enough_data = min(len(tokens_a), len(tokens_b)) >= minimum_tokens
            suspicious = enough_data and (jaccard >= 0.55 or containment >= 0.75 or (vector_score is not None and vector_score >= 0.92))
            comparisons.append({
                "vendors": [first.get("vendor_name", first.get("vendor_id")), second.get("vendor_name", second.get("vendor_id"))],
                "token_counts": [len(tokens_a), len(tokens_b)],
                "word_5gram_jaccard": round(jaccard, 5),
                "word_5gram_containment": round(containment, 5),
                "dense_embedding_cosine": round(vector_score, 5) if vector_score is not None else None,
                "screening_result": "HIGH_SIMILARITY_REVIEW" if suspicious else ("INSUFFICIENT_TEXT" if not enough_data else "NO_HIGH_SIMILARITY_SIGNAL"),
                "interpretation": "Kemiripan dapat berasal dari dokumen acuan, templat, atau persyaratan yang sama; perlu telaah manusia dan pembanding sumber.",
                "legal_caveat": "Indikator kemiripan merupakan sinyal anomali bukti untuk telaah auditor manusia (Human-in-the-Loop); bukan putusan hukum persekongkolan tender sesuai Pasal 22 UU 5/1999.",
            })
    return {
        "status": "screened" if len(vendors) > 1 else "insufficient_comparison_data",
        "compared_vendor_count": len(vendors),
        "comparisons": comparisons,
        "method": "Exact word 5-gram overlap; dense cosine is calculated only when compatible vectors are explicitly supplied.",
        "legal_notice": "AI tidak menetapkan status hukum kolusi secara sepihak. Seluruh temuan berstatus Indikator Kesamaan Bukti yang wajib diverifikasi Pokja/APIP.",
    }


def scan_contract_dilution(vendor_contract: str, baseline_contract: str) -> dict[str, Any]:
    if not baseline_contract.strip():
        return {"status": "baseline_not_provided", "findings": [], "interpretation": "Perbandingan redaksi membutuhkan baseline yang disediakan pengguna dan diverifikasi sumbernya."}
    vendor_lines = _sentences(vendor_contract)
    baseline_lines = _sentences(baseline_contract)
    findings: list[dict[str, Any]] = []
    for topic, terms in _CONTRACT_TOPICS.items():
        base_clause = _first_matching(baseline_lines, terms)
        vendor_clause = _first_matching(vendor_lines, terms)
        if base_clause and not vendor_clause:
            findings.append({
                "topic": topic,
                "signal": "BASELINE_CLAUSE_NOT_LOCATED_IN_VENDOR_TEXT",
                "baseline_quote": base_clause,
                "vendor_quote": None,
                "severity": "REVIEW",
                "description": "Klausul topik yang ada pada baseline tidak ditemukan secara tekstual pada naskah vendor yang dipasok.",
            })
        elif base_clause and vendor_clause and _has_weakened_terms(vendor_clause) and not _has_weakened_terms(base_clause):
            findings.append({
                "topic": topic,
                "signal": "POSSIBLE_REMEDY_LIMITATION_ADDED",
                "baseline_quote": base_clause,
                "vendor_quote": vendor_clause,
                "severity": "REVIEW",
                "description": "Naskah vendor memuat istilah pembatasan remediasi yang tidak tampak pada kutipan baseline terpilih.",
            })
        elif base_clause and vendor_clause and _normalize(base_clause) != _normalize(vendor_clause):
            findings.append({
                "topic": topic,
                "signal": "CLAUSE_TEXT_DIFFERS_FROM_BASELINE",
                "baseline_quote": base_clause,
                "vendor_quote": vendor_clause,
                "severity": "REVIEW",
                "description": "Redaksi klausul berbeda dari baseline; perbedaan belum diklasifikasikan sebagai pelanggaran.",
            })
    return {
        "status": "compared",
        "findings": findings,
        "interpretation": "Pemindaian kata kunci tidak menilai keabsahan hukum atau memastikan urutan versi; baseline bukan standar LKPP kecuali sumber dan versinya dibuktikan.",
    }


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD.finditer(text)]


def _ngrams(tokens: list[str], size: int = 5) -> set[tuple[str, ...]]:
    return {tuple(tokens[index:index + size]) for index in range(max(0, len(tokens) - size + 1))}


def _cosine(first: Any, second: Any) -> float | None:
    if not isinstance(first, list) or not isinstance(second, list) or not first or len(first) != len(second):
        return None
    try:
        a, b = [float(value) for value in first], [float(value) for value in second]
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in a + b):
        return None
    norm_a = math.sqrt(sum(value * value for value in a))
    norm_b = math.sqrt(sum(value * value for value in b))
    if norm_a == 0 or norm_b == 0:
        return None
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.;!?])\s+|\n+", text) if part.strip()]


def _first_matching(lines: list[str], terms: tuple[str, ...]) -> str | None:
    return next((line[:1000] for line in lines if any(term in line.casefold() for term in terms)), None)


def _has_weakened_terms(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in _WEAKENING_TERMS)


def _normalize(text: str) -> str:
    return " ".join(_WORD.findall(text.casefold()))
