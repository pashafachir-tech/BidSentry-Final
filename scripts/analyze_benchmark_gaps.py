#!/usr/bin/env python3
"""Empirical gap analyzer for BidSentry benchmark evaluations (Validation Set v1 & Narrative Set).

Runs the EvaluationEngine against all benchmark documents, compares expected vs actual
finding IDs, and tabulates root causes (Rule ID naming discrepancies, incidental findings,
and administrative slot incompleteness).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bidsentry.evaluators.engine import EvaluationEngine, EvaluationRequest


def analyze_dataset(dir_path: Path, dataset_name: str) -> list[dict[str, Any]]:
    engine = EvaluationEngine()
    files = sorted(dir_path.glob("*.json"))
    rows = []

    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        req_data = data.get("request", {})
        req = EvaluationRequest(**req_data)
        res = engine.evaluate(req)

        doc_id = data.get("id", f.stem)
        exp_verdict = data.get("expected_verdict", "")
        act_verdict = res.get("verdict", "")
        exp_findings = data.get("expected_findings", {})
        act_findings = {item["id"]: item.get("status", "") for item in res.get("findings", [])}

        fps = [fid for fid in act_findings if fid not in exp_findings or act_findings[fid] != exp_findings[fid]]
        fns = [fid for fid in exp_findings if fid not in act_findings or exp_findings[fid] != act_findings[fid]]

        # Classify root cause
        reasons = []
        # Check rule ID synonym/alias matches
        alias_map = {
            "SPEC-LOCKIN-PROC": "SPEC-LOCKIN-CPU",
            "PROC-TIMELINE-PREP": "PROC-TIMELINE-COMPRESSED",
            "PROC-TIMELINE-SANGGAH": "PROC-TIMELINE-COMPRESSED",
            "FIN-HPS-OVER-PAGU": "FIN-OVER-BUDGET",
            "FIN-BILLING-RATE": "FIN-MARKUP-RATE",
        }
        for fn in fns:
            if fn in alias_map and alias_map[fn] in act_findings:
                reasons.append(f"Perbedaan ID Aturan: label '{fn}' vs engine '{alias_map[fn]}'")
            else:
                reasons.append(f"Klausul '{fn}' tidak terdeteksi")

        for fp in fps:
            if fp in alias_map.values() and any(alias_map.get(fn) == fp for fn in fns):
                continue  # already counted as alias pair
            if fp in ("ADM-NPWP", "ADM-NIB", "ADM-KSWP", "ADM-SBU"):
                status = act_findings.get(fp, "")
                reasons.append(f"Pemeriksaan administratif dasar ({fp}: {status}) terpicu dari teks")
            elif fp == "CON-PENALTY":
                reasons.append("Klausul denda tanpa cap (CON-PENALTY) ada di teks draf kontrak namun tak tercatat di label")
            elif fp == "PROC-TIMELINE-COMPRESSED":
                reasons.append("Jadwal mepet terpicu dari teks dokumen pemilihan")
            else:
                reasons.append(f"Temuan tambahan '{fp}' ({act_findings.get(fp)})")

        if not fps and not fns:
            analysis = "Identik (100% Cocok)"
        else:
            analysis = "; ".join(reasons) if reasons else "Sesuai"

        rows.append({
            "doc_id": doc_id,
            "exp_verdict": exp_verdict,
            "act_verdict": act_verdict,
            "verdict_match": exp_verdict == act_verdict,
            "exp_findings": exp_findings,
            "act_findings": act_findings,
            "fps": fps,
            "fns": fns,
            "analysis": analysis,
        })

    return rows


def format_markdown_table(rows: list[dict[str, Any]], title: str) -> str:
    lines = [
        f"### {title}",
        "",
        "| Dokumen ID | Vonis (Exp / Act) | Finding ID Diharapkan | Finding ID Dihasilkan | Selisih (FP / FN) | Penyebab Nyata Berdasarkan Engine |",
        "| :--- | :---: | :--- | :--- | :--- | :--- |",
    ]
    for r in rows:
        v_str = f"`{r['exp_verdict']}` / `{r['act_verdict']}`"
        if r['verdict_match']:
            v_str += " ✅"
        else:
            v_str += " ❌"

        exp_str = ", ".join(f"`{k}`" for k in r["exp_findings"]) if r["exp_findings"] else "*(kosong)*"
        act_str = ", ".join(f"`{k}`" for k in r["act_findings"]) if r["act_findings"] else "*(kosong)*"
        
        diff_parts = []
        if r["fps"]:
            diff_parts.append(f"FP: {', '.join(f'`{x}`' for x in r['fps'])}")
        if r["fns"]:
            diff_parts.append(f"FN: {', '.join(f'`{x}`' for x in r['fns'])}")
        diff_str = "<br>".join(diff_parts) if diff_parts else "Nihil"

        lines.append(f"| `{r['doc_id']}` | {v_str} | {exp_str} | {act_str} | {diff_str} | {r['analysis']} |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    blind_rows = analyze_dataset(ROOT / "data" / "test_blind", "Validation Set v1 (10 Dokumen)")
    budget_rows = analyze_dataset(ROOT / "data" / "test_narrative_budget", "Narrative Budget Set (5 Dokumen)")

    print(format_markdown_table(blind_rows, "Tabel Evaluasi Finding Per-Dokumen: Validation Set v1 (10 Dokumen)"))
    print(format_markdown_table(budget_rows, "Tabel Evaluasi Finding Per-Dokumen: Narrative Budget Set (5 Dokumen)"))


if __name__ == "__main__":
    main()
