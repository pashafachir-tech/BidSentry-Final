"""Deterministic baseline-to-submitted-contract text comparison."""

from __future__ import annotations

import difflib
import re
from typing import Any


def diff_contracts(baseline_text: str, submitted_text: str) -> dict[str, Any]:
    """Return exact line changes and topic cues; this is not a legal opinion."""
    if not baseline_text.strip():
        return {"status": "baseline_not_provided", "changes": [], "findings": [], "interpretation": "Perbandingan membutuhkan baseline yang sumber dan versinya dapat diverifikasi."}
    baseline_lines = _lines(baseline_text)
    submitted_lines = _lines(submitted_text)
    matcher = difflib.SequenceMatcher(a=baseline_lines, b=submitted_lines, autojunk=False)
    changes: list[dict[str, Any]] = []
    for operation, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        changes.append({
            "operation": operation,
            "baseline_line_start": a_start + 1,
            "baseline_line_end": a_end,
            "submitted_line_start": b_start + 1,
            "submitted_line_end": b_end,
            "baseline_text": "\n".join(baseline_lines[a_start:a_end])[:4000] or None,
            "submitted_text": "\n".join(submitted_lines[b_start:b_end])[:4000] or None,
        })
    return {
        "status": "compared",
        "baseline_line_count": len(baseline_lines),
        "submitted_line_count": len(submitted_lines),
        "change_count": len(changes),
        "changes": changes,
        "findings": _topic_findings(baseline_lines, submitted_lines),
        "interpretation": "Perbedaan tekstual perlu dicocokkan dengan versi yang berlaku dan ditelaah manusia; perubahan tidak otomatis merupakan pelanggaran atau pengenceran kontrak.",
    }


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]


def _topic_findings(baseline: list[str], submitted: list[str]) -> list[dict[str, str]]:
    topics = {
        "LIQUIDATED_DAMAGES": ("denda keterlambatan", "liquidated damages", "late delivery"),
        "SLA_REMEDIES": ("service level", "service credit", "sla"),
        "TERMINATION": ("pemutusan", "pengakhiran", "termination", "wanprestasi"),
        "WARRANTY": ("garansi", "jaminan mutu", "warranty"),
    }
    findings: list[dict[str, str]] = []
    for topic, phrases in topics.items():
        baseline_quote = next((line for line in baseline if any(phrase in line.casefold() for phrase in phrases)), None)
        submitted_quote = next((line for line in submitted if any(phrase in line.casefold() for phrase in phrases)), None)
        if baseline_quote and not submitted_quote:
            findings.append({"topic": topic, "signal": "BASELINE_TOPIC_NOT_LOCATED", "baseline_quote": baseline_quote[:1000], "submitted_quote": ""})
        elif baseline_quote and submitted_quote and _normalize(baseline_quote) != _normalize(submitted_quote):
            findings.append({"topic": topic, "signal": "TOPIC_TEXT_DIFFERS", "baseline_quote": baseline_quote[:1000], "submitted_quote": submitted_quote[:1000]})
    return findings


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[\wÀ-ÿ]+", text.casefold()))
